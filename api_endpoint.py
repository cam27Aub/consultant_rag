"""
api_endpoint.py — ConsultantIQ RAG API for n8n integration.

Place in: C:\\Users\\merhi\\Desktop\\consultant_rag\\api_endpoint.py
Run locally: python api_endpoint.py
Deploy to Render: uvicorn api_endpoint:app --host 0.0.0.0 --port $PORT
"""

import sys
import io
import re
import contextlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn


# ── Models ──────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    answer: str
    mode_used: str
    sources: list[str] = []


# ── App ─────────────────────────────────────────────────────

app = FastAPI(title="ConsultantIQ API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Load retrievers at startup ──────────────────────────────

hybrid_retriever = None

@app.on_event("startup")
def load_retrievers():
    global hybrid_retriever
    print("Loading retrievers...")
    try:
        from hybrid_rag.query_hybrid import HybridRetriever
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            hybrid_retriever = HybridRetriever()
        print("  ✓ Hybrid retriever loaded (includes naive + graph)")
    except Exception as e:
        print(f"  ✗ Hybrid retriever failed: {e}")
    print("Ready.\n")


# ── Helper ──────────────────────────────────────────────────

def clean_answer(raw: str) -> str:
    """Strip debug/scoring lines from the RAG answer."""
    clean_lines = []
    for line in raw.split("\n"):
        stripped = line.strip()
        if stripped.startswith("═") or stripped.startswith("──"):
            continue
        if stripped.startswith("[") and "score=" in stripped:
            continue
        if "Embedding batch" in stripped:
            continue
        if stripped.startswith("? "):
            continue
        if re.match(r"^Mode:", stripped):
            continue
        if re.match(r"^\d+ nodes,", stripped):
            continue
        if "Naive RAG loaded" in stripped:
            continue
        if "Extracted terms:" in stripped:
            continue
        if "Found " in stripped and "seed entities" in stripped:
            continue
        if stripped.startswith("Graph:") or stripped.startswith("Naive RAG:"):
            continue
        clean_lines.append(line)

    result = "\n".join(clean_lines).strip()
    result = re.sub(r"^[═─\-=]{3,}\s*", "", result)
    result = re.sub(r"\s*[═─\-=]{3,}$", "", result)
    return result.strip()


def extract_sources(captured_output: str, answer: str) -> list[str]:
    """Extract unique source references as simple 'document / Page N' strings."""
    seen = set()
    sources = []

    # Parse naive-style chunk lines: [1] Lecture 2.pdf | Section | p7 | score=0.03
    for m in re.finditer(r'\[\d+\]\s+(.+?)\s*\|\s*.+?\|\s*p(\S+)', captured_output):
        doc, page = m.group(1).strip(), m.group(2).strip()
        key = f"{doc}|{page}"
        if key not in seen:
            seen.add(key)
            sources.append(f"{doc} / Page {page}")

    # Parse graph-style entity lines: (Source: filename.docx, p3)
    for m in re.finditer(r'\(Source:\s*(.+?),\s*p(\S+?)\)', captured_output + answer):
        doc, page = m.group(1).strip(), m.group(2).strip()
        key = f"{doc}|{page}"
        if key not in seen:
            seen.add(key)
            sources.append(f"{doc} / Page {page}")

    # Parse answer citations: [Source: filename, section, Page/Slide N] or [Source: filename, pN]
    for m in re.finditer(r'\[Source:\s*(.+?),\s*(?:.*?,\s*)?(?:Page|Slide|p)/?\.?\s*(\S+?)\]', answer):
        doc, page = m.group(1).strip(), m.group(2).strip()
        key = f"{doc}|{page}"
        if key not in seen:
            seen.add(key)
            sources.append(f"{doc} / Page {page}")

    return sources


def detect_mode_used(captured_output: str) -> str:
    """Parse captured stdout to determine which mode the hybrid engine chose."""
    if "Mode: HYBRID" in captured_output:
        return "hybrid (graph + naive)"
    elif "Mode: GRAPH" in captured_output:
        return "graph"
    elif "Mode: NAIVE" in captured_output:
        return "naive"
    return "hybrid"


# ── Endpoints ───────────────────────────────────────────────

@app.post("/query", response_model=QueryResponse)
def query_rag(request: QueryRequest):
    """
    Main query endpoint. No mode parameter needed.
    The hybrid engine automatically decides: graph, naive, or both.

    n8n calls:  POST /query  {"query": "user's question"}
    """
    if not hybrid_retriever:
        raise HTTPException(500, "Retriever not loaded")

    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            answer = hybrid_retriever.ask(request.query)

        captured = buf.getvalue()
        mode_used = detect_mode_used(captured)
        sources = extract_sources(captured, answer)
        clean = clean_answer(answer)

        if not clean:
            clean = answer.strip()

        return QueryResponse(
            answer=clean,
            mode_used=mode_used,
            sources=sources,
        )

    except Exception as e:
        raise HTTPException(500, f"Query failed: {str(e)}")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "retriever_loaded": hybrid_retriever is not None,
    }


# ── Run ─────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
