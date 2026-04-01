"""
retriever_graph.py — Graph RAG query engine.

Query flow:
  1. Extract key terms from the user's question (GPT-4o)
  2. Search graph for matching entity nodes
  3. Traverse neighbours (depth=2) to build a subgraph context
  4. Format subgraph as structured context
  5. GPT-4o generates a grounded answer from the graph context
"""
import json
import re
from openai import AzureOpenAI
from graph_rag.graph_store import GraphStore
from graph_rag import config_graph as config

EXTRACT_TERMS_PROMPT = """Extract the key entity names from this question that would appear as nodes in a knowledge graph about management consulting.
Return a JSON array of strings only. Example: ["Porter's Five Forces", "EBITDA", "McKinsey"]
Question: {question}"""

ANSWER_PROMPT = """You are ConsultantIQ Graph, a knowledge assistant that answers questions using a knowledge graph extracted from consulting documents.

You are given a subgraph of entities and relationships relevant to the user's question.

SUBGRAPH CONTEXT:
{context}

Rules:
1. Answer using ONLY the information in the subgraph above.
2. Explain how the entities and relationships connect to answer the question.
3. Cite entity names and relationship types where relevant.
4. If the graph does not contain enough information, say: "The knowledge graph does not contain sufficient information to answer this question."
5. Be concise and professional.

QUESTION: {question}
"""


class GraphRetriever:
    def __init__(self):
        self.client = AzureOpenAI(
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
        )
        self.store = GraphStore()

    def _extract_terms(self, question: str) -> list[str]:
        """Use GPT-4o to pull key entity terms from the question."""
        try:
            resp = self.client.chat.completions.create(
                model=config.AZURE_CHAT_DEPLOYMENT,
                messages=[{"role": "user", "content": EXTRACT_TERMS_PROMPT.format(question=question)}],
                temperature=0.0,
                max_tokens=200,
            )
            raw = resp.choices[0].message.content.strip()
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            terms = json.loads(raw)
            return terms if isinstance(terms, list) else []
        except Exception:
            # fallback: split question into words > 4 chars
            return [w for w in question.split() if len(w) > 4]

    def _build_context(self, subgraph: dict) -> str:
        """Format a subgraph dict into a readable context string for GPT-4o."""
        nodes = subgraph.get("nodes", [])
        edges = subgraph.get("edges", [])

        if not nodes:
            return "No relevant entities found in the knowledge graph."

        lines = ["ENTITIES:"]
        node_map = {}
        for n in nodes:
            node_map[n["id"]] = n["name"] or n["id"]
            lines.append(f'  • [{n["label"]}] {n["name"]} — {n["description"]} (Source: {n["source"]}, p{n["page"]})')

        if edges:
            lines.append("\nRELATIONSHIPS:")
            for e in edges:
                from_name = node_map.get(e["from"], e["from"])
                to_name   = node_map.get(e["to"],   e["to"])
                lines.append(f'  • {from_name} —[{e["type"]}]→ {to_name}')

        return "\n".join(lines)

    def retrieve(self, question: str, top_k: int = 5) -> dict:
        """
        Retrieve a subgraph relevant to the question.
        Returns dict with 'nodes', 'edges', and 'terms'.
        """
        terms = self._extract_terms(question)
        print(f"  Extracted terms: {terms}")

        # search graph for matching entities
        seed_entities = self.store.search_entities(terms, top_k=top_k)
        print(f"  Found {len(seed_entities)} seed entities")

        if not seed_entities:
            return {"nodes": [], "edges": [], "terms": terms}

        # expand each seed entity with neighbour traversal
        all_nodes, all_edges = [], []
        seen_ids = set()

        for entity in seed_entities:
            subgraph = self.store.get_neighbours(entity["id"], depth=2)
            for n in subgraph["nodes"]:
                if n["id"] not in seen_ids:
                    seen_ids.add(n["id"])
                    # Carry forward match score from seed entity
                    if n["id"] == entity["id"]:
                        n["_match_score"] = entity.get("_match_score", 0)
                    all_nodes.append(n)
            all_edges.extend(subgraph["edges"])

        return {"nodes": all_nodes, "edges": all_edges, "terms": terms}

    def ask(self, question: str, top_k: int = 5) -> str:
        """Full Graph RAG query — retrieve subgraph then generate answer."""
        subgraph = self.retrieve(question, top_k=top_k)
        context  = self._build_context(subgraph)

        print(f"\n{'='*60}")
        print(f"{question}")
        print(f"── {len(subgraph['nodes'])} nodes, {len(subgraph['edges'])} edges retrieved ──")

        response = self.client.chat.completions.create(
            model=config.AZURE_CHAT_DEPLOYMENT,
            messages=[
                {"role": "user", "content": ANSWER_PROMPT.format(
                    context=context, question=question
                )}
            ],
            temperature=0.1,
            max_tokens=800,
        )
        answer = response.choices[0].message.content.strip()
        print(answer)
        print("=" * 60)
        return answer

    def close(self):
        self.store.close()
