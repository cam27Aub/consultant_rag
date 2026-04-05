"""
api_endpoint.py — Lightweight API wrapper for ConsultantIQ RAG system.

Place this file in: C:\\Users\\merhi\\Desktop\\consultant_rag\\api_endpoint.py

Run with:
    pip install fastapi uvicorn
    cd C:\\Users\\merhi\\Desktop\\consultant_rag
    python api_endpoint.py

This exposes your existing RAG system as an API that n8n can call.
"""

import sys
import io
import contextlib
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# ── Models ──────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    mode: str = "hybrid"   # "hybrid", "naive", or "graph"
    top_k: int = 5

class QueryResponse(BaseModel):
    answer: str
    mode: str
    node_count: int = 0    # only relevant for graph/hybrid
    chunk_count: int = 0   # only relevant for naive

# ── App ─────────────────────────────────────────────────────

app = FastAPI(title="ConsultantIQ API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Load retrievers once at startup ─────────────────────────

hybrid_retriever = None
naive_retriever = None
graph_retriever = None

@app.on_event("startup")
def load_retrievers():
    global hybrid_retriever, naive_retriever, graph_retriever

    print("Loading retrievers...")

    try:
        from hybrid_rag.query_hybrid import HybridRetriever
        hybrid_retriever = HybridRetriever()
        print("  ✓ Hybrid retriever loaded")
    except Exception as e:
        print(f"  ✗ Hybrid retriever failed: {e}")

    try:
        from naive_rag.retriever import RAGRetriever
        naive_retriever = RAGRetriever()
        print("  ✓ Naive retriever loaded")
    except Exception as e:
        print(f"  ✗ Naive retriever failed: {e}")

    try:
        from graph_rag.retriever_graph import GraphRetriever
        graph_retriever = GraphRetriever()
        print("  ✓ Graph retriever loaded")
    except Exception as e:
        print(f"  ✗ Graph retriever failed: {e}")

    print("Retrievers ready.\n")


# ── Endpoints ───────────────────────────────────────────────

@app.post("/query", response_model=QueryResponse)
def query_rag(request: QueryRequest):
    """
    Main query endpoint. n8n calls this with:
    POST /query
    {"query": "user's question", "mode": "hybrid"}
    """
    try:
        if request.mode == "hybrid":
            if not hybrid_retriever:
                raise HTTPException(500, "Hybrid retriever not loaded")

            # Capture stdout since HybridRetriever prints to console
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                answer = hybrid_retriever.ask(request.query)

            return QueryResponse(
                answer=answer,
                mode="hybrid",
            )

        elif request.mode == "naive":
            if not naive_retriever:
                raise HTTPException(500, "Naive retriever not loaded")

            result = naive_retriever.ask(
                request.query,
                top_k=request.top_k,
                verbose=False,
            )
            return QueryResponse(
                answer=result["answer"],
                mode="naive",
                chunk_count=len(result.get("chunks", [])),
            )

        elif request.mode == "graph":
            if not graph_retriever:
                raise HTTPException(500, "Graph retriever not loaded")

            # Capture stdout since GraphRetriever prints to console
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                answer = graph_retriever.ask(request.query, top_k=request.top_k)

            return QueryResponse(
                answer=answer,
                mode="graph",
            )

        else:
            raise HTTPException(400, f"Unknown mode: {request.mode}. Use 'hybrid', 'naive', or 'graph'.")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Query failed: {str(e)}")


@app.get("/health")
def health():
    """Health check — n8n can ping this to verify the API is running."""
    return {
        "status": "ok",
        "hybrid": hybrid_retriever is not None,
        "naive": naive_retriever is not None,
        "graph": graph_retriever is not None,
    }


# ── Run ─────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
