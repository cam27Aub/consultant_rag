"""
api_endpoint.py — ConsultantIQ RAG API for n8n integration.

Place in: C:\\Users\\merhi\\Desktop\\consultant_rag\\api_endpoint.py
Run locally: python api_endpoint.py
Deploy to Render: uvicorn api_endpoint:app --host 0.0.0.0 --port $PORT
"""

import sys
import io
import re
import os
import base64
import contextlib
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse as StaticFileResponse, Response
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


# ── Auto-evaluation for real queries ────────────────────────

_GITHUB_API = "https://api.github.com"
_EVAL_LOG_PATH = Path(__file__).parent / "evaluation" / "results" / "query_log.json"

_EVAL_PROMPT = """You are a strict evaluation judge for a RAG system.
Given a QUESTION, CONTEXT (retrieved documents), and ANSWER, score on 3 metrics (0.0-1.0).

QUESTION: {question}

CONTEXT:
{context}

ANSWER:
{answer}

Rubrics:
- faithfulness: Is every claim in the answer supported by the provided context? (1.0 = fully grounded, 0.0 = answer contradicts or ignores context)
- answer_relevancy: Does the answer actually address what the question asked? (1.0 = directly answers, 0.0 = completely off-topic)
- context_precision: Is the retrieved context relevant and useful for answering this question? (1.0 = context is perfectly relevant, 0.0 = context is irrelevant)

Return ONLY valid JSON: {{"faithfulness": X, "answer_relevancy": X, "context_precision": X}}"""


def _eval_load_log() -> list:
    token = GITHUB_TOKEN
    repo  = GITHUB_REPO
    if token and repo:
        try:
            import requests as _req
            url = f"{_GITHUB_API}/repos/{repo}/contents/evaluation/results/query_log.json"
            headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
            r = _req.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                return _json.loads(base64.b64decode(r.json()["content"]).decode("utf-8"))
        except Exception:
            pass
    if _EVAL_LOG_PATH.exists():
        try:
            return _json.loads(_EVAL_LOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _eval_save_log(log: list):
    content_str = _json.dumps(log, indent=2, ensure_ascii=False)
    # Always write locally first (backup in case GitHub fails)
    try:
        _EVAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _EVAL_LOG_PATH.write_text(content_str, encoding="utf-8")
    except Exception as e:
        print(f"[eval-log] local write failed: {e}")

    token = GITHUB_TOKEN
    repo  = GITHUB_REPO
    if not (token and repo):
        return
    try:
        import requests as _req
        url = f"{_GITHUB_API}/repos/{repo}/contents/evaluation/results/query_log.json"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        # Fetch current SHA (needed to update existing file)
        r = _req.get(url, headers=headers, timeout=10)
        sha = r.json().get("sha", "") if r.status_code == 200 else ""
        payload = {
            "message": "analytics: log real query eval",
            "content": base64.b64encode(content_str.encode("utf-8")).decode("utf-8"),
            "branch": "master",
        }
        if sha:
            payload["sha"] = sha
        put_r = _req.put(url, headers=headers, json=payload, timeout=30)
        if put_r.status_code not in (200, 201):
            print(f"[eval-log] GitHub PUT failed: {put_r.status_code} - {put_r.text[:200]}")
    except Exception as e:
        print(f"[eval-log] GitHub push failed: {e}")


def _auto_evaluate(question: str, answer: str, context: str,
                   mode: str, response_time: float, sources: list):
    """Background task: LLM-as-judge on a real UI query → appended to analytics log."""
    try:
        import config
        from openai import AzureOpenAI
        client = AzureOpenAI(
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
        )
        resp = client.chat.completions.create(
            model=config.AZURE_CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": _EVAL_PROMPT.format(
                question=question[:500],
                context=context[:6000],
                answer=answer[:3000],
            )}],
            temperature=0.0,
            max_tokens=150,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$",     "", raw)
        scores = _json.loads(raw)
        entry = {
            "question":          question,
            "effective_q":       question,
            "timestamp":         datetime.now().isoformat(timespec="seconds"),
            "mode":              mode,
            "response_time":     round(response_time, 2),
            "num_chunks":        len(sources),
            "answer_length":     len(answer),
            "sources":           sources,
            "test_run":          False,   # real UI query, not a test
            # RAGAS metrics
            "faithfulness":      round(float(scores.get("faithfulness",      0)), 2),
            "answer_relevancy":  round(float(scores.get("answer_relevancy",  0)), 2),
            "context_precision": round(float(scores.get("context_precision", 0)), 2),
        }
        log = _eval_load_log()
        log.append(entry)
        _eval_save_log(log)
    except Exception as e:
        print(f"[auto-eval] skipped: {e}")


# ── Endpoints ───────────────────────────────────────────────

@app.post("/query", response_model=QueryResponse)
def query_rag(request: QueryRequest, background_tasks: BackgroundTasks):
    """
    Main query endpoint. No mode parameter needed.
    The hybrid engine automatically decides: graph, naive, or both.
    Every response is automatically evaluated in the background and
    logged to the analytics query log.

    n8n calls:  POST /query  {"query": "user's question"}
    """
    if not hybrid_retriever:
        raise HTTPException(500, "Retriever not loaded")

    try:
        t0 = time.time()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            answer = hybrid_retriever.ask(request.query)
        response_time = time.time() - t0

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

        # Auto-evaluate in background — doesn't slow down the response
        background_tasks.add_task(
            _auto_evaluate,
            request.query, clean, captured, mode_used, response_time, sources,
        )

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
def get_analytics(refresh: bool = False):
    """Return RAG analytics summary + base64 chart images.
    Pass ?refresh=true to bypass the 5-minute cache.
    """
    try:
        import analytics_rag
        return analytics_rag.get_analytics(bust_cache=refresh)
    except Exception as e:
        raise HTTPException(500, f"Analytics failed: {str(e)}")


# ── RAG Document Management ──────────────────────────────────

DOCS_DIR        = Path(__file__).parent / "sample_docs"
INGEST_STATUS_F = Path(__file__).parent / "ingest_status.json"
SUPPORTED_EXTS  = {".pdf", ".pptx", ".docx"}
_ingest_lock    = threading.Lock()

# ── GitHub persistence ────────────────────────────────────────
GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO   = os.getenv("GITHUB_REPO", "cam27Aub/consultant_rag")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "master")


def _commit_to_github(filename: str, content: bytes) -> bool:
    """Commit a file to sample_docs/ in the GitHub repo. Returns True on success."""
    if not GITHUB_TOKEN:
        return False
    import requests as _req
    path    = f"sample_docs/{filename}"
    url     = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    # Get existing SHA if the file already exists (required for updates)
    sha = None
    r = _req.get(url, headers=headers, params={"ref": GITHUB_BRANCH}, timeout=10)
    if r.status_code == 200:
        sha = r.json().get("sha")

    body: dict = {
        "message": f"docs: add {filename} via ConsultantIQ upload",
        "content": base64.b64encode(content).decode("utf-8"),
        "branch":  GITHUB_BRANCH,
    }
    if sha:
        body["sha"] = sha

    resp = _req.put(url, headers=headers, json=body, timeout=30)
    return resp.status_code in (200, 201)


def _write_status(status: str, message: str = ""):
    try:
        INGEST_STATUS_F.write_text(
            _json.dumps({"status": status, "message": message}),
            encoding="utf-8"
        )
    except Exception:
        pass


def _list_github_docs():
    """Return list of supported files in sample_docs/ from the GitHub repo."""
    import requests as _req
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/sample_docs"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    r = _req.get(url, headers=headers, params={"ref": GITHUB_BRANCH}, timeout=10)
    if r.status_code != 200:
        return []
    return [
        item for item in r.json()
        if item.get("type") == "file"
        and Path(item["name"]).suffix.lower() in SUPPORTED_EXTS
    ]


def _run_ingest():
    """Download docs from GitHub into a temp dir, run ingest, then clean up.
    Releases lock when done — Render filesystem is never used for permanent storage.
    """
    import tempfile
    import requests as _req

    tmp_dir = None
    try:
        # ── 1. List files from GitHub ──────────────────────────────
        _write_status("running", "Fetching document list from GitHub…")
        items = _list_github_docs()
        if not items:
            _write_status("error", "No documents found in GitHub repo (sample_docs/ is empty).")
            return

        # ── 2. Download to a temp directory ───────────────────────
        tmp_dir = tempfile.mkdtemp(prefix="rag_ingest_")
        _write_status("running", f"Downloading {len(items)} document(s)…")
        for item in items:
            dest = Path(tmp_dir) / item["name"]
            dl = _req.get(item["download_url"], timeout=120)
            dl.raise_for_status()
            dest.write_bytes(dl.content)
            print(f"[ingest] downloaded {item['name']}")

        # ── 3. Run ingest.py against the temp dir (stream stdout → status) ──
        _write_status("running", "Running ingestion pipeline…")
        proc = subprocess.Popen(
            ["python", "naive_rag/ingest.py", "--no-vision", "--docs", tmp_dir],
            cwd=str(Path(__file__).parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,   # merge stderr into stdout
            text=True,
            bufsize=1,
        )
        last_line = "Running ingestion pipeline…"
        deadline = __import__("time").time() + 1800
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                last_line = line
                _write_status("running", line)
            if __import__("time").time() > deadline:
                proc.kill()
                _write_status("error", "Ingestion timed out after 30 minutes.")
                return
        proc.wait()
        if proc.returncode == 0:
            _write_status("done", "Ingestion completed successfully.")
        else:
            _write_status("error", f"Pipeline failed: {last_line}")

    except subprocess.TimeoutExpired:
        _write_status("error", "Ingestion timed out after 30 minutes.")
    except Exception as e:
        _write_status("error", str(e))
    finally:
        # ── 4. Clean up temp dir ───────────────────────────────────
        if tmp_dir:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
        try:
            _ingest_lock.release()
        except RuntimeError:
            pass


@app.get("/documents")
def list_documents():
    """List documents from the GitHub repo (source of truth — no local files needed)."""
    if not GITHUB_TOKEN:
        # Fallback: scan local sample_docs/ if no GitHub token configured
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
    try:
        items = _list_github_docs()
        return {"files": [
            {
                "name": item["name"],
                "type": Path(item["name"]).suffix.upper().lstrip("."),
                "size_kb": round(item.get("size", 0) / 1024, 1),
            }
            for item in sorted(items, key=lambda x: x["name"])
        ]}
    except Exception as e:
        raise HTTPException(502, f"Could not reach GitHub: {e}")


@app.post("/upload-documents")
async def upload_documents(background_tasks: BackgroundTasks, files: list[UploadFile] = File(...)):
    """Upload documents directly to GitHub — no permanent local storage on Render."""
    saved = []
    errors = []
    for upload in files:
        ext = Path(upload.filename or "").suffix.lower()
        if ext not in SUPPORTED_EXTS:
            errors.append(f"{upload.filename}: unsupported type (use PDF, PPTX, DOCX)")
            continue
        try:
            content = await upload.read()
            if GITHUB_TOKEN:
                # Commit synchronously so the file is in GitHub before we return
                ok = _commit_to_github(upload.filename, content)
                saved.append({"name": upload.filename, "github": ok})
                if not ok:
                    errors.append(f"{upload.filename}: GitHub commit failed")
            else:
                # No GitHub token — fall back to local storage
                DOCS_DIR.mkdir(exist_ok=True)
                (DOCS_DIR / (upload.filename or "upload")).write_bytes(content)
                saved.append({"name": upload.filename, "github": False})
        except Exception as e:
            errors.append(f"{upload.filename}: {e}")
    return {"saved": saved, "errors": errors}


@app.delete("/documents/{filename}")
def delete_document(filename: str, background_tasks: BackgroundTasks):
    """Delete a document from GitHub (and local fallback if present)."""
    if not GITHUB_TOKEN:
        dest = DOCS_DIR / filename
        if not dest.exists():
            raise HTTPException(404, f"{filename} not found")
        dest.unlink()
        return {"deleted": filename}
    # Delete from GitHub
    background_tasks.add_task(_delete_from_github, filename)
    return {"deleted": filename}


def _delete_from_github(filename: str) -> bool:
    """Delete a file from the GitHub repo."""
    if not GITHUB_TOKEN:
        return False
    import requests as _req
    path    = f"sample_docs/{filename}"
    url     = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    r = _req.get(url, headers=headers, params={"ref": GITHUB_BRANCH}, timeout=10)
    if r.status_code != 200:
        return False
    sha  = r.json().get("sha")
    resp = _req.delete(url, headers=headers, timeout=30, json={
        "message": f"docs: remove {filename} via ConsultantIQ",
        "sha":     sha,
        "branch":  GITHUB_BRANCH,
    })
    return resp.status_code == 200


@app.post("/ingest")
def trigger_ingest():
    """Trigger the RAG ingestion pipeline as a background job.
    Returns immediately — actual work runs in a background thread.
    """
    # Check status file first (survives across requests)
    if INGEST_STATUS_F.exists():
        try:
            current = _json.loads(INGEST_STATUS_F.read_text(encoding="utf-8"))
            if current.get("status") == "running":
                return {"status": "already_running", "message": "Ingestion is already in progress."}
        except Exception:
            pass

    # Try to acquire lock (non-blocking) to prevent concurrent starts
    if not _ingest_lock.acquire(blocking=False):
        return {"status": "already_running", "message": "Ingestion is already in progress."}

    # Write running status before spawning thread so polls see it immediately
    _write_status("running", "Ingestion started…")

    t = threading.Thread(target=_run_ingest, daemon=True)
    t.start()
    # Lock is intentionally held — _run_ingest releases it when done
    return {"status": "started", "message": "Ingestion pipeline started."}


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
        # Always serve index.html with no-cache so browsers pick up new bundles
        resp = StaticFileResponse(frontend_dist / "index.html")
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp


# ── Run ─────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
