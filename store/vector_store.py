import json
import numpy as np
from pathlib import Path
import config


class LocalVectorStore:
    def __init__(self, store_dir: str = config.STORE_DIR):
        self.store_dir    = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.chunks_path  = self.store_dir / "chunks.json"
        self.vectors_path = self.store_dir / "embeddings.npy"
        self.chunks: list[dict]  = []
        self.vectors: np.ndarray = np.empty((0, 0), dtype=np.float32)

    def save(self, chunks):
        chunk_dicts = [c.to_dict() for c in chunks]
        vectors = np.array([c.embedding for c in chunks], dtype=np.float32)
        with open(self.chunks_path, "w", encoding="utf-8") as f:
            json.dump(chunk_dicts, f, indent=2, ensure_ascii=False)
        np.save(str(self.vectors_path), vectors)
        self.chunks  = chunk_dicts
        self.vectors = vectors
        print(f"  Saved {len(chunks)} chunks -> {self.store_dir}")

    def load(self):
        if not self.chunks_path.exists():
            raise FileNotFoundError(f"No index at {self.store_dir}. Run ingest.py first.")
        with open(self.chunks_path, encoding="utf-8") as f:
            self.chunks = json.load(f)
        self.vectors = np.load(str(self.vectors_path))
        print(f"  Loaded {len(self.chunks)} chunks from {self.store_dir}")

    def vector_search(self, query_vec, top_k=config.TOP_K, filter_tag=None):
        if self.vectors.shape[0] == 0:
            return []
        qv = np.array(query_vec, dtype=np.float32)
        scores = self.vectors @ qv
        if filter_tag:
            mask = np.array([
                1 if c.get("metadata", {}).get("project_tag") == filter_tag else 0
                for c in self.chunks
            ], dtype=np.float32)
            scores = scores * mask
        top_idx = np.argsort(scores)[::-1][:top_k]
        results = []
        for i in top_idx:
            c = dict(self.chunks[i])
            c["_score_vector"] = float(scores[i])
            results.append(c)
        return results

    def fulltext_search(self, query, top_k=config.TOP_K):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        texts = [c.get("cleaned_text") or c.get("chunk_text", "") for c in self.chunks]
        if not texts:
            return []
        tfidf = TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True)
        all_texts = texts + [query]
        mat = tfidf.fit_transform(all_texts)
        scores = cosine_similarity(mat[-1], mat[:-1])[0]
        top_idx = np.argsort(scores)[::-1][:top_k]
        results = []
        for i in top_idx:
            c = dict(self.chunks[i])
            c["_score_fulltext"] = float(scores[i])
            results.append(c)
        return results

    def hybrid_search(self, query_vec, query_text, top_k=config.TOP_K, rrf_k=config.RRF_K):
        vec_res  = self.vector_search(query_vec,  top_k=top_k * 3)
        text_res = self.fulltext_search(query_text, top_k=top_k * 3)
        def rrf(rank): return 1.0 / (rrf_k + rank + 1)
        scores = {}
        id_to_chunk = {}
        for rank, c in enumerate(vec_res):
            cid = c.get("id", str(rank))
            scores[cid] = scores.get(cid, 0) + rrf(rank)
            id_to_chunk[cid] = c
        for rank, c in enumerate(text_res):
            cid = c.get("id", str(rank))
            scores[cid] = scores.get(cid, 0) + rrf(rank)
            id_to_chunk[cid] = c
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for cid, rrf_score in ranked:
            c = dict(id_to_chunk[cid])
            c["_score_rrf"]      = round(rrf_score, 5)
            c["_score_vector"]   = id_to_chunk[cid].get("_score_vector", 0)
            c["_score_fulltext"] = id_to_chunk[cid].get("_score_fulltext", 0)
            results.append(c)
        return results

    def stats(self):
        sources = {}
        tags = {}
        for c in self.chunks:
            sources[c["source"]] = sources.get(c["source"], 0) + 1
            tag = c.get("metadata", {}).get("project_tag", "unknown")
            tags[tag] = tags.get(tag, 0) + 1
        return {
            "total_chunks": len(self.chunks),
            "embed_dim":    self.vectors.shape[1] if self.vectors.ndim > 1 else 0,
            "sources":      sources,
            "project_tags": tags,
        }


class AzureSearchStore:
    def __init__(self):
        from azure.search.documents import SearchClient
        from azure.search.documents.indexes import SearchIndexClient
        from azure.search.documents.indexes.models import (
            SearchIndex, SimpleField, SearchableField, SearchField,
            SearchFieldDataType, VectorSearch, HnswAlgorithmConfiguration,
            VectorSearchProfile, SemanticConfiguration, SemanticSearch,
            SemanticPrioritizedFields, SemanticField
        )
        from azure.core.credentials import AzureKeyCredential

        credential = AzureKeyCredential(config.AZURE_SEARCH_KEY)
        self.index_client = SearchIndexClient(
            endpoint=config.AZURE_SEARCH_ENDPOINT,
            credential=credential
        )
        self.search_client = SearchClient(
            endpoint=config.AZURE_SEARCH_ENDPOINT,
            index_name=config.AZURE_SEARCH_INDEX,
            credential=credential
        )
        self._index_models = {
            "SearchIndex": SearchIndex,
            "SimpleField": SimpleField,
            "SearchableField": SearchableField,
            "SearchField": SearchField,
            "SearchFieldDataType": SearchFieldDataType,
            "VectorSearch": VectorSearch,
            "HnswAlgorithmConfiguration": HnswAlgorithmConfiguration,
            "VectorSearchProfile": VectorSearchProfile,
            "SemanticConfiguration": SemanticConfiguration,
            "SemanticSearch": SemanticSearch,
            "SemanticPrioritizedFields": SemanticPrioritizedFields,
            "SemanticField": SemanticField,
        }

    def create_index(self):
        m = self._index_models
        fields = [
            m["SimpleField"](name="id",           type=m["SearchFieldDataType"].String, key=True),
            m["SearchableField"](name="chunk_text",type=m["SearchFieldDataType"].String, analyzer_name="standard.lucene"),
            m["SearchableField"](name="cleaned_text",type=m["SearchFieldDataType"].String, analyzer_name="standard.lucene"),
            m["SimpleField"](name="source",        type=m["SearchFieldDataType"].String, filterable=True, facetable=True),
            m["SimpleField"](name="doc_type",      type=m["SearchFieldDataType"].String, filterable=True),
            m["SimpleField"](name="page",          type=m["SearchFieldDataType"].Int32,  filterable=True, sortable=True),
            m["SearchableField"](name="section",   type=m["SearchFieldDataType"].String),
            m["SimpleField"](name="project_tag",   type=m["SearchFieldDataType"].String, filterable=True, facetable=True),
            m["SimpleField"](name="doc_date",      type=m["SearchFieldDataType"].String, filterable=True),
            m["SimpleField"](name="summary",       type=m["SearchFieldDataType"].String),
            m["SearchField"](
                name="embedding",
                type=m["SearchFieldDataType"].Collection(m["SearchFieldDataType"].Single),
                searchable=True,
                vector_search_dimensions=config.AZURE_EMBED_DIM,
                vector_search_profile_name="hnsw-profile"
            ),
        ]
        vector_search = m["VectorSearch"](
            algorithms=[m["HnswAlgorithmConfiguration"](name="hnsw-algo")],
            profiles=[m["VectorSearchProfile"](name="hnsw-profile", algorithm_configuration_name="hnsw-algo")]
        )
        semantic_config = m["SemanticConfiguration"](
            name="semantic-config",
            prioritized_fields=m["SemanticPrioritizedFields"](
                content_fields=[m["SemanticField"](field_name="chunk_text")],
                keywords_fields=[m["SemanticField"](field_name="section"),
                                  m["SemanticField"](field_name="source")]
            )
        )
        index = m["SearchIndex"](
            name=config.AZURE_SEARCH_INDEX,
            fields=fields,
            vector_search=vector_search,
            semantic_search=m["SemanticSearch"](configurations=[semantic_config])
        )
        self.index_client.create_or_update_index(index)
        print(f"  Azure AI Search index '{config.AZURE_SEARCH_INDEX}' ready")

    def save(self, chunks):
        """Upload all chunks to Azure AI Search in batches of 100."""
        docs = []
        for c in chunks:
            d = c.to_dict()
            meta = d.pop("metadata", {}) or {}
            flat = {
                "id":           d["id"],
                "chunk_text":   d["chunk_text"],
                "cleaned_text": d.get("cleaned_text", ""),
                "source":       d["source"],
                "doc_type":     d["doc_type"],
                "page":         d["page"],
                "section":      d["section"],
                "project_tag":  meta.get("project_tag", "general"),
                "doc_date":     meta.get("doc_date", ""),
                "summary":      d.get("summary", ""),
                "embedding":    d["embedding"],
            }
            docs.append(flat)

        BATCH = 100
        total = 0
        for i in range(0, len(docs), BATCH):
            batch = docs[i:i+BATCH]
            result = self.search_client.upload_documents(documents=batch)
            succeeded = sum(1 for r in result if r.succeeded)
            total += succeeded
            print(f"  Uploaded {total}/{len(docs)} chunks")
        print(f"  All {total} chunks indexed in Azure AI Search")

    def load(self):
        """No-op for Azure — index lives in the cloud."""
        count = self.search_client.get_document_count()
        print(f"  Azure AI Search: {count} chunks in index '{config.AZURE_SEARCH_INDEX}'")

    def vector_search(self, query_vec, top_k=config.TOP_K, filter_tag=None):
        from azure.search.documents.models import VectorizedQuery
        vector_query = VectorizedQuery(
            vector=query_vec,
            k_nearest_neighbors=top_k,
            fields="embedding"
        )
        filter_expr = f"project_tag eq '{filter_tag}'" if filter_tag else None
        results = self.search_client.search(
            search_text=None,
            vector_queries=[vector_query],
            filter=filter_expr,
            top=top_k,
            select=["id","chunk_text","cleaned_text","source","doc_type",
                    "page","section","project_tag","summary"]
        )
        return [self._to_dict(r, "_score_vector") for r in results]

    def fulltext_search(self, query, top_k=config.TOP_K):
        results = self.search_client.search(
            search_text=query,
            top=top_k,
            select=["id","chunk_text","cleaned_text","source","doc_type",
                    "page","section","project_tag","summary"]
        )
        return [self._to_dict(r, "_score_fulltext") for r in results]

    def hybrid_search(self, query_vec, query_text, top_k=config.TOP_K, rrf_k=None):
        from azure.search.documents.models import VectorizedQuery
        vector_query = VectorizedQuery(
            vector=query_vec,
            k_nearest_neighbors=top_k * 3,
            fields="embedding"
        )
        results = self.search_client.search(
            search_text=query_text,
            vector_queries=[vector_query],
            query_type="semantic",
            semantic_configuration_name="semantic-config",
            top=top_k,
            select=["id","chunk_text","cleaned_text","source","doc_type",
                    "page","section","project_tag","summary"]
        )
        return [self._to_dict(r, "_score_rrf") for r in results]

    def _to_dict(self, r, score_key):
        d = dict(r)
        d[score_key] = d.pop("@search.score", 0) or d.pop("@search.reranker_score", 0) or 0
        d["metadata"] = {"project_tag": d.get("project_tag", "")}
        return d

    def stats(self):
        count = self.search_client.get_document_count()
        return {
            "total_chunks": count,
            "embed_dim":    config.AZURE_EMBED_DIM,
            "sources":      {},
            "project_tags": {},
        }


def get_store():
    if config.MODE == "azure":
        return AzureSearchStore()
    return LocalVectorStore()
