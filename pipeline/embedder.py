import json
import numpy as np
import pickle
import os
from pathlib import Path
from pipeline.chunker import ChunkUnit
import config


class LocalEmbedder:
    def __init__(self, n_components: int = config.LOCAL_EMBED_DIM):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.decomposition import TruncatedSVD
        from sklearn.preprocessing import Normalizer
        from sklearn.pipeline import make_pipeline
        self.n_components = n_components
        self.tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_df=0.85,
                                      sublinear_tf=True, strip_accents="unicode")
        self.svd   = TruncatedSVD(n_components=n_components, random_state=42)
        self.norm  = Normalizer(copy=False)
        self.pipeline = make_pipeline(self.tfidf, self.svd, self.norm)
        self.is_fitted = False

    def fit(self, texts):
        print(f"  Fitting LSA on {len(texts)} chunks (dim={self.n_components})...")
        self.pipeline.fit(texts)
        self.is_fitted = True

    def embed(self, texts):
        if not self.is_fitted:
            raise RuntimeError("Call fit() before embed()")
        return self.pipeline.transform(texts)

    def embed_one(self, text):
        return self.embed([text])[0].tolist()

    def cosine_distance(self, a, b):
        va = np.array(self.embed_one(a))
        vb = np.array(self.embed_one(b))
        return round(1.0 - float(np.dot(va, vb)), 4)


class AzureEmbedder:
    def __init__(self):
        from openai import AzureOpenAI
        self.client = AzureOpenAI(
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
        )
        self.deployment = config.AZURE_EMBED_DEPLOYMENT

    def embed_batch(self, texts: list[str], batch_size: int = 16) -> list[list[float]]:
        import time
        all_vecs = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            print(f"  Embedding batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1} "
                  f"({len(batch)} chunks)...")
            for attempt in range(3):
                try:
                    resp = self.client.embeddings.create(
                        model=self.deployment, input=batch
                    )
                    all_vecs.extend([item.embedding for item in resp.data])
                    break
                except Exception as e:
                    if attempt < 2:
                        wait = 20 * (attempt + 1)
                        print(f"  Rate limit — retrying in {wait}s... ({e})")
                        time.sleep(wait)
                    else:
                        raise
        return all_vecs

    def embed_one(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]


_local_embedder_instance = None


def get_embedder():
    global _local_embedder_instance
    if config.MODE == "azure":
        return AzureEmbedder()
    if _local_embedder_instance is None:
        _local_embedder_instance = LocalEmbedder()
    return _local_embedder_instance


def save_embedder(path: str = None):
    """Only needed in local mode."""
    global _local_embedder_instance
    if config.MODE == "azure":
        return
    if _local_embedder_instance is None or not _local_embedder_instance.is_fitted:
        return
    save_path = path or os.path.join(config.STORE_DIR, "embedder.pkl")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "wb") as f:
        pickle.dump(_local_embedder_instance.pipeline, f)
    print(f"  Embedder model saved → {save_path}")


def load_embedder(path: str = None):
    """
    Azure mode: returns a fresh AzureEmbedder (no disk state needed).
    Local mode: loads the fitted LSA pipeline from disk.
    """
    global _local_embedder_instance
    if config.MODE == "azure":
        return AzureEmbedder()
    load_path = path or os.path.join(config.STORE_DIR, "embedder.pkl")
    if not os.path.exists(load_path):
        raise FileNotFoundError(
            f"No saved embedder at {load_path}. Run ingest.py first."
        )
    emb = LocalEmbedder()
    with open(load_path, "rb") as f:
        emb.pipeline = pickle.load(f)
    emb.is_fitted = True
    _local_embedder_instance = emb
    return emb


def embed_chunks(chunks: list[ChunkUnit]) -> list[ChunkUnit]:
    """Embed all chunks. Azure: batched API. Local: LSA."""
    texts = [c.cleaned_text or c.chunk_text for c in chunks]

    if config.MODE == "azure":
        emb = AzureEmbedder()
        vecs = emb.embed_batch(texts)
        for chunk, vec in zip(chunks, vecs):
            chunk.embedding = vec

    else:
        emb = get_embedder()
        if not emb.is_fitted:
            emb.fit(texts)
        print(f"  Embedding {len(chunks)} chunks (local LSA)...")
        vecs_mat = emb.embed(texts)
        for chunk, vec in zip(chunks, vecs_mat):
            chunk.embedding = vec.tolist()

    return chunks
