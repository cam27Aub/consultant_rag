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

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse as StaticFileResponse
from pydantic import BaseModel
import uvicorn
import shutil
import subprocess
import threading
import json as _json
from typing import Optional
from docx_generator import app as docx_app
import chat_memory


# ── Models ──────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    answer: str
    mode_used: str
    sources: list[str] = []

class ConversationIn(BaseModel):
    id: str
    title: str = "New Chat"
    messages: list[dict] = []
    createdAt: int = 0
    updatedAt: int = 0

class PreferencesIn(BaseModel):
    preferences: dict


# ── App ─────────────────────────────────────────────────────

app = FastAPI(title="ConsultantIQ API", version="2.0")
app.mount("/docx", docx_app)

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

    # Initialize chat memory (Cosmos DB)
    chat_memory.init_db()
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

    # Parse answer citations: [Source: filename.ext, section, Page/Slide N] or [Source: filename, pN]
    # Use greedy match for filename to capture full extensions like .docx
    for m in re.finditer(r'\[Source:\s*(.+?\.\w+),\s*(?:.*?,\s*)?(?:Page|Slide|p)/?\.?\s*(\S+?)\]', answer):
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

        # Remove echoed question from start of answer
        q_lower = request.query.strip().lower()
        lines = clean.split("\n")
        if lines and lines[0].strip().lower().rstrip("?").strip() == q_lower.rstrip("?").strip():
            clean = "\n".join(lines[1:]).strip()

        if not clean:
            clean = answer.strip()

        return QueryResponse(
            answer=clean,
            mode_used=mode_used,
            sources=sources,
        )

    except Exception as e:
        raise HTTPException(500, f"Query failed: {str(e)}")


# ── Chat Memory Endpoints ──────────────────────────────────

@app.get("/conversations")
def list_conversations():
    """List all conversations (without messages)."""
    return chat_memory.list_conversations()


@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    """Get a single conversation with all messages."""
    convo = chat_memory.get_conversation(conversation_id)
    if not convo:
        raise HTTPException(404, "Conversation not found")
    return convo


@app.post("/conversations")
def sync_conversation(convo: ConversationIn):
    """Create or update a conversation (upsert)."""
    success = chat_memory.save_conversation(convo.model_dump())
    if not success:
        raise HTTPException(500, "Failed to save conversation")
    return {"status": "ok"}


@app.delete("/conversations/{conversation_id}")
def remove_conversation(conversation_id: str):
    """Delete a conversation and its messages."""
    success = chat_memory.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(500, "Failed to delete conversation")
    return {"status": "ok"}


@app.get("/user-profile")
def get_user_profile():
    """Get all user preferences."""
    return chat_memory.get_preferences()


@app.put("/user-profile")
def update_user_profile(data: PreferencesIn):
    """Update user preferences."""
    success = chat_memory.save_preferences(data.preferences)
    if not success:
        raise HTTPException(500, "Failed to save preferences")
    return {"status": "ok"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "retriever_loaded": hybrid_retriever is not None,
        "memory_enabled": chat_memory._is_ready(),
    }


@app.get("/analytics")
def get_analytics():
    """Return RAG analytics summary + base64 chart images."""
    try:
        import analytics_rag
        return analytics_rag.get_analytics()
    except Exception as e:
        raise HTTPException(500, f"Analytics failed: {str(e)}")


# ── RAG Document Management ──────────────────────────────────

DOCS_DIR        = Path(__file__).parent / "sample_docs"
INGEST_STATUS_F = Path(__file__).parent / "ingest_status.json"
SUPPORTED_EXTS  = {".pdf", ".pptx", ".docx"}
_ingest_lock    = threading.Lock()


def _write_status(status: str, message: str = ""):
    try:
        INGEST_STATUS_F.write_text(
            _json.dumps({"status": status, "message": message}),
            encoding="utf-8"
        )
    except Exception:
        pass


def _run_ingest():
    """Run ingestion pipeline in background thread."""
    _write_status("running", "Ingestion started…")
    try:
        result = subprocess.run(
            ["python", "naive_rag/ingest.py", "--no-vision"],
            cwd=str(Path(__file__).parent),
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode == 0:
            _write_status("done", "Ingestion completed successfully.")
        else:
            _write_status("error", result.stderr[-500:] if result.stderr else "Unknown error")
    except subprocess.TimeoutExpired:
        _write_status("error", "Ingestion timed out after 10 minutes.")
    except Exception as e:
        _write_status("error", str(e))


@app.get("/documents")
def list_documents():
    """List all files currently in sample_docs/."""
    DOCS_DIR.mkdir(exist_ok=True)
    files = []
    for f in sorted(DOCS_DIR.iterdir()):
        if f.suffix.lower() in SUPPORTED_EXTS:
            files.append({
                "name": f.name,
                "type": f.suffix.upper().lstrip("."),
                "size_kb": round(f.stat().st_size / 1024, 1),
            })
    return {"files": files}


@app.post("/upload-documents")
async def upload_documents(files: list[UploadFile] = File(...)):
    """Upload one or more documents to sample_docs/."""
    DOCS_DIR.mkdir(exist_ok=True)
    saved = []
    errors = []
    for upload in files:
        ext = Path(upload.filename or "").suffix.lower()
        if ext not in SUPPORTED_EXTS:
            errors.append(f"{upload.filename}: unsupported type (use PDF, PPTX, DOCX)")
            continue
        dest = DOCS_DIR / (upload.filename or "upload")
        try:
            with open(dest, "wb") as out:
                shutil.copyfileobj(upload.file, out)
            saved.append(upload.filename)
        except Exception as e:
            errors.append(f"{upload.filename}: {e}")
    return {"saved": saved, "errors": errors}


@app.post("/ingest")
def trigger_ingest():
    """Trigger the RAG ingestion pipeline as a background job."""
    if not _ingest_lock.acquire(blocking=False):
        return {"status": "already_running", "message": "Ingestion is already in progress."}
    try:
        current = {}
        if INGEST_STATUS_F.exists():
            try:
                current = _json.loads(INGEST_STATUS_F.read_text(encoding="utf-8"))
            except Exception:
                pass
        if current.get("status") == "running":
            _ingest_lock.release()
            return {"status": "already_running", "message": "Ingestion is already in progress."}
        t = threading.Thread(target=_run_ingest, daemon=True)
        t.start()
        return {"status": "started", "message": "Ingestion pipeline started."}
    except Exception as e:
        _ingest_lock.release()
        raise HTTPException(500, str(e))
    finally:
        try:
            _ingest_lock.release()
        except RuntimeError:
            pass


@app.get("/ingest-status")
def ingest_status():
    """Check the status of the last ingestion run."""
    if not INGEST_STATUS_F.exists():
        return {"status": "idle", "message": "No ingestion has been run yet."}
    try:
        return _json.loads(INGEST_STATUS_F.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "unknown", "message": "Could not read status file."}


# ── Frontend (serve React build) ─────────────────────────────

frontend_dist = Path(__file__).parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = frontend_dist / full_path
        if file_path.exists() and file_path.is_file():
            return StaticFileResponse(file_path)
        return StaticFileResponse(frontend_dist / "index.html")


# ── Run ─────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
