import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import streamlit as st
import os
import json
import time
import tempfile
import io
import contextlib
import base64
import requests as http_requests
from datetime import datetime


# ── Auto-evaluation: fast local scoring (no LLM calls) ───────────────
import re
import math


def _tokenize(text: str) -> list[str]:
    """Simple word tokenizer — lowercase, alpha-only, 3+ chars."""
    return [w for w in re.findall(r'[a-z]{3,}', text.lower())]


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0


def _rouge_l(reference: str, hypothesis: str) -> tuple[float, float]:
    """ROUGE-L precision and recall using longest common subsequence."""
    ref_words = _tokenize(reference)
    hyp_words = _tokenize(hypothesis)
    if not ref_words or not hyp_words:
        return 0.0, 0.0
    # LCS via DP
    m, n = len(ref_words), len(hyp_words)
    # Limit to first 500 words each to keep it fast
    ref_words = ref_words[:500]
    hyp_words = hyp_words[:500]
    m, n = len(ref_words), len(hyp_words)
    prev = [0] * (n + 1)
    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(curr[j - 1], prev[j])
        prev = curr
    lcs_len = prev[n]
    precision = lcs_len / n if n > 0 else 0.0
    recall = lcs_len / m if m > 0 else 0.0
    return precision, recall


def _keyword_recall(context: str, answer: str) -> float:
    """What % of important context keywords appear in the answer."""
    # Extract keywords: words appearing in context but not common stopwords
    stopwords = {"the", "and", "for", "are", "with", "that", "this", "from", "have", "has",
                 "been", "was", "were", "will", "can", "which", "their", "they", "also",
                 "more", "than", "into", "such", "each", "about", "between", "should",
                 "these", "other", "not", "but", "its", "all", "any", "our", "your"}
    ctx_words = set(_tokenize(context)) - stopwords
    ans_words = set(_tokenize(answer))
    if not ctx_words:
        return 0.0
    return len(ctx_words & ans_words) / len(ctx_words)


def _evaluate_answer(question: str, context: str, answer: str) -> dict:
    """Fast local evaluation — no LLM calls. Uses embeddings + text overlap."""
    try:
        # Embedding-based scores (uses cached embedder if available)
        embed_ground = 0.0
        embed_relev = 0.0
        try:
            import config
            from openai import AzureOpenAI
            client = AzureOpenAI(
                azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
                api_key=config.AZURE_OPENAI_KEY,
                api_version=config.AZURE_OPENAI_API_VERSION,
            )
            resp = client.embeddings.create(
                model=config.AZURE_EMBED_DEPLOYMENT,
                input=[answer[:2000], context[:3000], question[:500]],
            )
            vec_answer  = resp.data[0].embedding
            vec_context = resp.data[1].embedding
            vec_question = resp.data[2].embedding
            embed_ground = _cosine_sim(vec_answer, vec_context)
            embed_relev  = _cosine_sim(vec_answer, vec_question)
        except Exception:
            pass

        # ROUGE-L: precision = hallucination check, recall = completeness check
        rouge_precision, rouge_recall = _rouge_l(context, answer)

        # Keyword recall
        kw_recall = _keyword_recall(context, answer)

        # Combine scores:
        # Groundedness: embedding similarity between answer and context
        groundedness = round(embed_ground, 2)

        # Relevancy: embedding similarity between answer and question
        relevancy = round(embed_relev, 2)

        # Completeness: blend of keyword recall and ROUGE recall
        completeness = round(0.5 * kw_recall + 0.5 * rouge_recall, 2)

        # Hallucination (inverted: 1.0 = no hallucination):
        # ROUGE precision = how much of answer is found in context
        hallucination = round(rouge_precision, 2)

        return {
            "groundedness":  groundedness,
            "relevancy":     relevancy,
            "completeness":  completeness,
            "hallucination": hallucination,
        }
    except Exception:
        return {"groundedness": 0, "relevancy": 0, "completeness": 0, "hallucination": 0}

# ── Persistent query log (GitHub-backed) ──────────────────────────────
LOG_PATH = Path(__file__).parent.parent / "evaluation" / "results" / "query_log.json"

_GITHUB_API = "https://api.github.com"


def _gh_token():
    try:
        return st.secrets.get("GITHUB_TOKEN", os.getenv("GITHUB_TOKEN", ""))
    except Exception:
        return os.getenv("GITHUB_TOKEN", "")


def _gh_repo():
    try:
        return st.secrets.get("GITHUB_REPO", os.getenv("GITHUB_REPO", ""))
    except Exception:
        return os.getenv("GITHUB_REPO", "")


def _gh_headers():
    return {
        "Authorization": f"token {_gh_token()}",
        "Accept": "application/vnd.github.v3+json",
    }


def _load_log() -> list[dict]:
    """Load query log from GitHub repo, fallback to local file."""
    token, repo = _gh_token(), _gh_repo()
    if token and repo:
        try:
            url = f"{_GITHUB_API}/repos/{repo}/contents/evaluation/results/query_log.json"
            r = http_requests.get(url, headers=_gh_headers(), timeout=10)
            if r.status_code == 200:
                content = base64.b64decode(r.json()["content"]).decode("utf-8")
                return json.loads(content)
            return []
        except Exception:
            return []
    # Fallback: local file
    if LOG_PATH.exists():
        try:
            return json.loads(LOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_log(log: list[dict]):
    """Save query log to GitHub repo, fallback to local file."""
    content_str = json.dumps(log, indent=2, ensure_ascii=False)
    token, repo = _gh_token(), _gh_repo()
    if token and repo:
        try:
            url = f"{_GITHUB_API}/repos/{repo}/contents/evaluation/results/query_log.json"
            # Get current file SHA (needed for update)
            r = http_requests.get(url, headers=_gh_headers(), timeout=10)
            sha = r.json().get("sha", "") if r.status_code == 200 else ""

            payload = {
                "message": "Update query log",
                "content": base64.b64encode(content_str.encode("utf-8")).decode("utf-8"),
                "branch": "master",
            }
            if sha:
                payload["sha"] = sha

            http_requests.put(url, headers=_gh_headers(), json=payload, timeout=10)
            return
        except Exception:
            pass
    # Fallback: local file
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(content_str, encoding="utf-8")


def _append_log(entry: dict):
    log = _load_log()
    log.append(entry)
    _save_log(log)


# ── Persistent chat log (GitHub-backed) ───────────────────────────────
CHAT_LOG_FILE = "evaluation/results/chat_log.json"


def _load_chat_log() -> list[dict]:
    """Load chat log from GitHub repo, fallback to local file."""
    token, repo = _gh_token(), _gh_repo()
    if token and repo:
        try:
            url = f"{_GITHUB_API}/repos/{repo}/contents/{CHAT_LOG_FILE}"
            r = http_requests.get(url, headers=_gh_headers(), timeout=10)
            if r.status_code == 200:
                content = base64.b64decode(r.json()["content"]).decode("utf-8")
                return json.loads(content)
            return []
        except Exception:
            return []
    # Fallback: local file
    local = Path(__file__).parent.parent / CHAT_LOG_FILE
    if local.exists():
        try:
            return json.loads(local.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_chat_log(log: list[dict]):
    """Save chat log to GitHub repo, fallback to local file."""
    content_str = json.dumps(log, indent=2, ensure_ascii=False)
    token, repo = _gh_token(), _gh_repo()
    if token and repo:
        try:
            url = f"{_GITHUB_API}/repos/{repo}/contents/{CHAT_LOG_FILE}"
            r = http_requests.get(url, headers=_gh_headers(), timeout=10)
            sha = r.json().get("sha", "") if r.status_code == 200 else ""

            payload = {
                "message": "Update chat log",
                "content": base64.b64encode(content_str.encode("utf-8")).decode("utf-8"),
                "branch": "master",
            }
            if sha:
                payload["sha"] = sha

            http_requests.put(url, headers=_gh_headers(), json=payload, timeout=10)
            return
        except Exception:
            pass
    # Fallback: local file
    local = Path(__file__).parent.parent / CHAT_LOG_FILE
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(content_str, encoding="utf-8")


def _append_chat(entry: dict):
    log = _load_chat_log()
    log.append(entry)
    _save_chat_log(log)


# ── Conversation sessions (ChatGPT-style) ────────────────────────────
SESSIONS_FILE = "evaluation/results/chat_sessions.json"


def _load_sessions() -> dict:
    """Load all chat sessions from GitHub. Returns {session_id: {title, messages, updated}}."""
    token, repo = _gh_token(), _gh_repo()
    if token and repo:
        try:
            url = f"{_GITHUB_API}/repos/{repo}/contents/{SESSIONS_FILE}"
            r = http_requests.get(url, headers=_gh_headers(), timeout=10)
            if r.status_code == 200:
                content = base64.b64decode(r.json()["content"]).decode("utf-8")
                return json.loads(content)
            return {}
        except Exception:
            return {}
    local = Path(__file__).parent.parent / SESSIONS_FILE
    if local.exists():
        try:
            return json.loads(local.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_sessions(sessions: dict):
    """Save all chat sessions to GitHub."""
    content_str = json.dumps(sessions, indent=2, ensure_ascii=False)
    token, repo = _gh_token(), _gh_repo()
    if token and repo:
        try:
            url = f"{_GITHUB_API}/repos/{repo}/contents/{SESSIONS_FILE}"
            r = http_requests.get(url, headers=_gh_headers(), timeout=10)
            sha = r.json().get("sha", "") if r.status_code == 200 else ""
            payload = {
                "message": "Update chat sessions",
                "content": base64.b64encode(content_str.encode("utf-8")).decode("utf-8"),
                "branch": "master",
            }
            if sha:
                payload["sha"] = sha
            http_requests.put(url, headers=_gh_headers(), json=payload, timeout=10)
            return
        except Exception:
            pass
    local = Path(__file__).parent.parent / SESSIONS_FILE
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(content_str, encoding="utf-8")


def _save_current_session():
    """Save the current session's messages to persistent storage."""
    if not st.session_state.messages:
        return
    sid = st.session_state.get("session_id", "")
    if not sid:
        return
    sessions = _load_sessions()
    # Title = first user message (truncated)
    first_q = ""
    for m in st.session_state.messages:
        if m["role"] == "user":
            first_q = m["content"][:60]
            break
    # Store only serializable fields
    stored_msgs = []
    for m in st.session_state.messages:
        stored_msgs.append({
            "role":        m["role"],
            "content":     m["content"],
            "rag_mode":    m.get("rag_mode", ""),
            "reformulated": m.get("reformulated", False),
            "used_memory": m.get("used_memory", False),
        })
    sessions[sid] = {
        "title":   first_q or "Untitled",
        "updated": datetime.now().isoformat(timespec="seconds"),
        "messages": stored_msgs,
    }
    _save_sessions(sessions)


# ── Page config ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ConsultantIQ",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
  #MainMenu, footer { visibility: hidden; }
  /* Keep sidebar toggle button visible */
  [data-testid="stSidebarCollapsedControl"] { visibility: visible !important; z-index: 999; }
  section[data-testid="stSidebar"] > div { padding: 1.5rem 1rem; }

  .top-bar {
    background: #1E3A5F;
    color: white;
    padding: 18px 28px;
    border-radius: 10px;
    margin-bottom: 24px;
  }
  .top-bar h1 { margin: 0; font-size: 22px; font-weight: 700; }
  .top-bar span { font-size: 13px; color: #93C5FD; }

  .msg-user {
    background: #EFF6FF;
    border: 1px solid #BFDBFE;
    border-radius: 12px 12px 2px 12px;
    padding: 12px 16px;
    margin: 8px 0;
    max-width: 80%;
    margin-left: auto;
    font-size: 14px;
    color: #1E3A5F;
  }
  .msg-assistant {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 12px 12px 12px 2px;
    padding: 14px 18px;
    margin: 8px 0;
    max-width: 90%;
    font-size: 14px;
    color: #111827;
    line-height: 1.6;
  }

  .citation-card {
    background: white;
    border: 1px solid #E2E8F0;
    border-left: 4px solid #1E3A5F;
    border-radius: 6px;
    padding: 10px 14px;
    margin: 6px 0;
    font-size: 12px;
  }
  .citation-card .src  { font-weight: 700; color: #1E3A5F; }
  .citation-card .meta { color: #64748B; margin-top: 2px; }
  .citation-card .snippet { color: #374151; margin-top: 6px; font-style: italic; line-height: 1.5; }

  .score-badge {
    display: inline-block;
    background: #EFF6FF;
    color: #1D4ED8;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 20px;
    margin-left: 8px;
  }

  .badge-reformulated {
    display: inline-block;
    background: #FEF9C3;
    color: #854D0E;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 10px;
    border-radius: 20px;
    margin-left: 6px;
  }
  .badge-memory {
    display: inline-block;
    background: #F3E8FF;
    color: #6B21A8;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 10px;
    border-radius: 20px;
    margin-left: 6px;
  }
  .badge-mode {
    display: inline-block;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 10px;
    border-radius: 20px;
    margin-left: 6px;
  }
  .badge-naive   { background: #DBEAFE; color: #1E40AF; }
  .badge-graph   { background: #D1FAE5; color: #065F46; }
  .badge-hybrid  { background: #FDE68A; color: #92400E; }
  .badge-web     { background: #E0E7FF; color: #3730A3; }

  .upload-info {
    background: #F0FDF4;
    border: 1px solid #BBF7D0;
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 13px;
    color: #166534;
    margin-top: 8px;
  }

  .sidebar-label {
    font-size: 11px;
    font-weight: 700;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 8px;
    margin-top: 16px;
  }

  .stButton > button {
    background: #1E3A5F;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: 600;
    width: 100%;
  }
  .stButton > button:hover { background: #2E5F8A; }
  hr { border: none; border-top: 1px solid #E2E8F0; margin: 16px 0; }

  .analytics-card {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 16px 20px;
    margin: 8px 0;
    text-align: center;
  }
  .analytics-card .value { font-size: 28px; font-weight: 700; color: #1E3A5F; }
  .analytics-card .label { font-size: 12px; color: #64748B; margin-top: 2px; }

  .source-card {
    background: white;
    border: 1px solid #E2E8F0;
    border-left: 4px solid #3730A3;
    border-radius: 6px;
    padding: 10px 14px;
    margin: 6px 0;
    font-size: 12px;
  }
  .source-card .src-name { font-weight: 700; color: #3730A3; }
  .source-card .src-url { color: #6B7280; font-size: 11px; margin-top: 2px; }
  .source-card .src-snippet { color: #374151; margin-top: 6px; font-style: italic; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
#  LOADERS (cached)
# ══════════════════════════════════════════════════════════════════════

@st.cache_resource(show_spinner=False)
def load_naive_rag():
    try:
        import config
        from pipeline.cracker   import DocumentCracker
        from pipeline.chunker   import SentenceChunker
        from pipeline.enricher  import ChunkEnricher
        from pipeline.embedder  import AzureEmbedder
        from store.vector_store import AzureSearchStore
        from naive_rag.retriever import RAGRetriever

        vision = None
        try:
            from pipeline.vision_processor import VisionProcessor
            vision = VisionProcessor()
        except ImportError:
            pass

        return {
            "config":    config,
            "cracker":   DocumentCracker(),
            "chunker":   SentenceChunker(chunk_words=getattr(config, "CHUNK_SIZE", 400)),
            "enricher":  ChunkEnricher(),
            "embedder":  AzureEmbedder(),
            "store":     AzureSearchStore(),
            "retriever": RAGRetriever(),
            "vision":    vision,
        }
    except Exception as e:
        return {"error": str(e)}


@st.cache_resource(show_spinner=False)
def load_graph_rag():
    try:
        import asyncio, sys
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        from graph_rag.retriever_graph import GraphRetriever
        return {"retriever": GraphRetriever()}
    except Exception as e:
        return {"error": str(e)}


@st.cache_resource(show_spinner=False)
def load_hybrid_rag():
    try:
        import asyncio, sys
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        from hybrid_rag.query_hybrid import HybridRetriever
        return {"retriever": HybridRetriever()}
    except Exception as e:
        return {"error": str(e)}


@st.cache_resource(show_spinner=False)
def load_web_agent():
    try:
        from web_scraper.search_agent import SearchAgent
        return {"agent": SearchAgent()}
    except Exception as e:
        return {"error": str(e)}


# ── Session state ──────────────────────────────────────────────────────
if "messages"    not in st.session_state: st.session_state.messages    = []
if "ingest_log"  not in st.session_state: st.session_state.ingest_log  = []
if "page"        not in st.session_state: st.session_state.page        = "chat"
if "session_id"  not in st.session_state:
    import uuid
    st.session_state.session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]


# ── Top bar ────────────────────────────────────────────────────────────
st.markdown("""
<div class="top-bar">
  <h1>ConsultantIQ</h1>
  <span>RAG-powered knowledge assistant &nbsp;&middot;&nbsp; Naive RAG &middot; Graph RAG &middot; Hybrid RAG &middot; Web Research</span>
</div>
""", unsafe_allow_html=True)


# ── Sidebar ────────────────────────────────────────────────────────────
with st.sidebar:

    # Navigation
    st.markdown('<div class="sidebar-label">Navigation</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Chat", use_container_width=True):
            st.session_state.page = "chat"
            st.rerun()
    with col2:
        if st.button("Analytics", use_container_width=True):
            st.session_state.page = "analytics"
            st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Chat History (ChatGPT-style) ──────────────────────────
    st.markdown('<div class="sidebar-label">Chat History</div>', unsafe_allow_html=True)
    import uuid

    if st.button("+ New Chat", use_container_width=True):
        # Save current session before starting new one
        _save_current_session()
        st.session_state.messages = []
        st.session_state.session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        st.session_state.page = "chat"
        st.rerun()

    # Load past sessions
    past_sessions = _load_sessions()
    if past_sessions:
        # Sort by updated time, newest first
        sorted_sessions = sorted(past_sessions.items(), key=lambda x: x[1].get("updated", ""), reverse=True)
        for sid, sdata in sorted_sessions[:15]:
            title = sdata.get("title", "Untitled")
            is_current = (sid == st.session_state.get("session_id", ""))
            col_chat, col_del = st.columns([5, 1])
            with col_chat:
                label = f"{'▶ ' if is_current else ''}{title}"
                if st.button(label, key=f"sess_{sid}", use_container_width=True):
                    if not is_current:
                        _save_current_session()
                        st.session_state.session_id = sid
                        st.session_state.messages = sdata.get("messages", [])
                        st.session_state.page = "chat"
                        st.rerun()
            with col_del:
                if st.button("🗑", key=f"del_{sid}"):
                    sessions = _load_sessions()
                    sessions.pop(sid, None)
                    _save_sessions(sessions)
                    # If deleting current session, start a new one
                    if is_current:
                        st.session_state.messages = []
                        st.session_state.session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
                    st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    # RAG Mode
    st.markdown('<div class="sidebar-label">RAG Mode</div>', unsafe_allow_html=True)
    rag_mode = st.selectbox(
        "Select RAG engine",
        ["Naive RAG", "Graph RAG", "Hybrid RAG", "Web Research"],
        label_visibility="collapsed",
    )

    st.markdown("<hr>", unsafe_allow_html=True)

    # Upload (only for Naive RAG / Graph RAG)
    if rag_mode in ("Naive RAG", "Graph RAG", "Hybrid RAG"):
        st.markdown('<div class="sidebar-label">Upload Documents</div>', unsafe_allow_html=True)
        uploaded = st.file_uploader(
            label="Add to knowledge base",
            type=["pdf", "pptx", "docx"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )

        if uploaded:
            if st.button("Ingest Documents"):
                naive = load_naive_rag()
                if "error" in naive:
                    st.error(f"RAG not loaded: {naive['error']}")
                else:
                    progress = st.progress(0, text="Starting...")
                    log = []
                    for i, f in enumerate(uploaded):
                        progress.progress(i / len(uploaded), text=f"Processing {f.name}...")
                        try:
                            suffix = Path(f.name).suffix
                            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                                tmp.write(f.read())
                                tmp_path = Path(tmp.name)

                            units = naive["cracker"].crack(tmp_path)

                            if naive.get("vision") and suffix.lower() in {".pdf", ".pptx", ".docx"}:
                                for u in units:
                                    desc = naive["vision"].describe_page(tmp_path, u.page)
                                    if desc:
                                        u.text += "\n\n[VISUAL CONTENT ON THIS PAGE]\n" + desc

                            chunks = []
                            for u in units:
                                chunks.extend(naive["chunker"].chunk(u))
                            chunks = [naive["enricher"].enrich(c) for c in chunks]

                            texts = [c.cleaned_text for c in chunks]
                            vecs  = naive["embedder"].embed_batch(texts)
                            for c, v in zip(chunks, vecs):
                                c.embedding = v
                                c.source    = f.name

                            naive["store"].upload_chunks(chunks)
                            os.unlink(tmp_path)
                            log.append(f"{f.name} — {len(chunks)} chunks indexed")
                        except Exception as e:
                            log.append(f"{f.name} — {str(e)}")

                    progress.progress(1.0, text="Done!")
                    st.session_state.ingest_log = log

        if st.session_state.ingest_log:
            st.markdown(
                '<div class="upload-info">' + "<br>".join(st.session_state.ingest_log) + "</div>",
                unsafe_allow_html=True,
            )

        st.markdown("<hr>", unsafe_allow_html=True)

    # Settings
    st.markdown('<div class="sidebar-label">Settings</div>', unsafe_allow_html=True)
    top_k         = st.slider("Chunks to retrieve (top-K)", 1, 10, 5)
    memory_window = st.slider("Conversation memory (turns)", 0, 20, 15)
    show_chunks   = st.toggle("Show retrieved chunks", value=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("Clear conversation"):
        _save_current_session()
        st.session_state.messages = []
        st.session_state.session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        st.rerun()

    # Status
    st.markdown('<div class="sidebar-label">Status</div>', unsafe_allow_html=True)
    if rag_mode == "Naive RAG":
        r = load_naive_rag()
        if "error" in r:
            st.error(r["error"])
        else:
            st.success("Naive RAG connected")
    elif rag_mode == "Graph RAG":
        r = load_graph_rag()
        if "error" in r:
            st.error(r["error"])
        else:
            st.success("Graph RAG connected (Cosmos DB)")
    elif rag_mode == "Hybrid RAG":
        r = load_hybrid_rag()
        if "error" in r:
            st.error(r["error"])
        else:
            st.success("Hybrid RAG connected")
    elif rag_mode == "Web Research":
        r = load_web_agent()
        if "error" in r:
            st.error(r["error"])
        else:
            st.success("Web Research agent connected")


# ══════════════════════════════════════════════════════════════════════
#  ANALYTICS PAGE
# ══════════════════════════════════════════════════════════════════════
if st.session_state.page == "analytics":
    st.markdown("### Analytics")
    log = _load_log()

    if not log:
        st.info("No queries logged yet. Ask some questions first!")
    else:
        import pandas as pd
        from collections import Counter

        total_queries  = len(log)
        avg_time       = sum(e.get("response_time", 0) for e in log) / total_queries
        scores         = [e.get("avg_score", 0) for e in log if e.get("avg_score")]
        avg_score      = sum(scores) / len(scores) if scores else 0

        # Evaluation averages
        ground_vals = [e.get("groundedness", 0) for e in log if e.get("groundedness")]
        relev_vals  = [e.get("relevancy", 0) for e in log if e.get("relevancy")]
        compl_vals  = [e.get("completeness", 0) for e in log if e.get("completeness")]
        halluc_vals = [e.get("hallucination", 0) for e in log if e.get("hallucination")]
        avg_ground  = sum(ground_vals) / len(ground_vals) if ground_vals else 0
        avg_relev   = sum(relev_vals) / len(relev_vals) if relev_vals else 0
        avg_compl   = sum(compl_vals) / len(compl_vals) if compl_vals else 0
        avg_halluc  = sum(halluc_vals) / len(halluc_vals) if halluc_vals else 0

        # ── KPI Row 1: System metrics ────────────────────────
        st.markdown("**System Metrics**")
        c1, c2, c3, c4 = st.columns(4)
        for col, val, label in [
            (c1, str(total_queries),       "Total Queries"),
            (c2, f"{avg_time:.1f}s",       "Avg Response Time"),
            (c3, f"{avg_score:.4f}",       "Avg Retrieval Score"),
            (c4, f"{len(set(e.get('mode','') for e in log))}", "Modes Used"),
        ]:
            col.markdown(
                f'<div class="analytics-card">'
                f'<div class="value">{val}</div>'
                f'<div class="label">{label}</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── KPI Row 2: Quality metrics ───────────────────────
        st.markdown("**Answer Quality Metrics** (Embedding + ROUGE-L + Keyword Overlap)")
        q1, q2, q3, q4 = st.columns(4)
        for col, val, label, color in [
            (q1, f"{avg_ground:.2f}",  "Groundedness",      "#22C55E"),
            (q2, f"{avg_relev:.2f}",   "Relevancy",         "#3B82F6"),
            (q3, f"{avg_compl:.2f}",   "Completeness",      "#F59E0B"),
            (q4, f"{avg_halluc:.2f}",  "No Hallucination",  "#EF4444"),
        ]:
            col.markdown(
                f'<div class="analytics-card">'
                f'<div class="value" style="color:{color}">{val}</div>'
                f'<div class="label">{label}</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Per-mode quality breakdown ────────────────────────
        st.markdown("**Quality Scores by RAG Mode**")
        mode_metrics = {}
        for e in log:
            mode = e.get("mode", "Unknown")
            if mode not in mode_metrics:
                mode_metrics[mode] = {"ground": [], "relev": [], "compl": [], "halluc": [], "time": []}
            if e.get("groundedness"):
                mode_metrics[mode]["ground"].append(e["groundedness"])
            if e.get("relevancy"):
                mode_metrics[mode]["relev"].append(e["relevancy"])
            if e.get("completeness"):
                mode_metrics[mode]["compl"].append(e["completeness"])
            if e.get("hallucination"):
                mode_metrics[mode]["halluc"].append(e["hallucination"])
            mode_metrics[mode]["time"].append(e.get("response_time", 0))

        quality_rows = []
        for mode, m in mode_metrics.items():
            quality_rows.append({
                "Mode": mode,
                "Queries": len(m["time"]),
                "Avg Time (s)": round(sum(m["time"]) / len(m["time"]), 1) if m["time"] else 0,
                "Groundedness": round(sum(m["ground"]) / len(m["ground"]), 2) if m["ground"] else "—",
                "Relevancy": round(sum(m["relev"]) / len(m["relev"]), 2) if m["relev"] else "—",
                "Completeness": round(sum(m["compl"]) / len(m["compl"]), 2) if m["compl"] else "—",
                "No Hallucination": round(sum(m["halluc"]) / len(m["halluc"]), 2) if m["halluc"] else "—",
            })
        st.dataframe(pd.DataFrame(quality_rows), use_container_width=True, hide_index=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Two columns: Mode distribution + Sources ──────────
        left, right = st.columns(2)

        with left:
            st.markdown("**RAG Mode Distribution**")
            mode_counts = Counter(e.get("mode", "unknown") for e in log)
            for mode_name, count in mode_counts.most_common():
                pct = count / total_queries
                st.markdown(f"**{mode_name}** — {count} queries ({pct:.0%})")
                st.progress(pct)

        with right:
            st.markdown("**Top 5 Queried Sources**")
            source_counter = Counter()
            for e in log:
                for s in e.get("sources", []):
                    source_counter[s] += 1
            if source_counter:
                for src, cnt in source_counter.most_common(5):
                    st.markdown(f"- **{src}** — {cnt} hits")
            else:
                st.markdown("_No source data yet_")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Response Time per Prompt by Mode (line chart) ─────
        st.markdown("**Response Time per Prompt by RAG Mode**")
        mode_series = {}
        for mode in ["Naive RAG", "Graph RAG", "Hybrid RAG"]:
            mode_times = [e.get("response_time", 0) for e in log if e.get("mode") == mode]
            if mode_times:
                mode_series[mode] = mode_times
        if mode_series:
            # Pad shorter lists with None so all columns align
            max_len = max(len(v) for v in mode_series.values())
            chart_data = {}
            for mode, times in mode_series.items():
                chart_data[mode] = times + [None] * (max_len - len(times))
            df_chart = pd.DataFrame(chart_data)
            df_chart.index = df_chart.index + 1  # prompts start at 1
            df_chart.index.name = "Prompt #"
            st.line_chart(df_chart, use_container_width=True)
            st.caption("**Horizontal axis:** Prompt number &nbsp;&nbsp;|&nbsp;&nbsp; **Vertical axis:** Response time (seconds)")

            # Summary table
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**Response Time Summary**")
            time_summary = []
            for mode in ["Naive RAG", "Graph RAG", "Hybrid RAG"]:
                mode_times = [e.get("response_time", 0) for e in log if e.get("mode") == mode]
                if mode_times:
                    time_summary.append({
                        "Mode": mode,
                        "Min (s)": round(min(mode_times), 1),
                        "Avg (s)": round(sum(mode_times) / len(mode_times), 1),
                        "Max (s)": round(max(mode_times), 1),
                        "Queries": len(mode_times),
                    })
            if time_summary:
                st.dataframe(pd.DataFrame(time_summary), use_container_width=True, hide_index=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Recent Queries with evaluation scores ─────────────
        st.markdown("**Recent Queries**")
        rows = []
        for e in reversed(log[-50:]):
            rows.append({
                "Question":        e.get("question", "")[:60],
                "Mode":            e.get("mode", ""),
                "Time (s)":        round(e.get("response_time", 0), 1),
                "Groundedness":    e.get("groundedness", "—"),
                "Relevancy":       e.get("relevancy", "—"),
                "Completeness":    e.get("completeness", "—"),
                "Hallucination":   e.get("hallucination", "—"),
                "Timestamp":       e.get("timestamp", ""),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.stop()


# ══════════════════════════════════════════════════════════════════════
#  CHAT PAGE
# ══════════════════════════════════════════════════════════════════════

MODE_BADGE_MAP = {
    "Naive RAG":    "naive",
    "Graph RAG":    "graph",
    "Hybrid RAG":   "hybrid",
    "Web Research":  "web",
}

for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f'<div class="msg-user">{msg["content"]}</div>', unsafe_allow_html=True)
    else:
        badges = ""
        mode_cls = MODE_BADGE_MAP.get(msg.get("rag_mode", ""), "naive")
        badges += f'<span class="badge-mode badge-{mode_cls}">{msg.get("rag_mode", "")}</span>'
        if msg.get("reformulated"):
            badges += '<span class="badge-reformulated">reformulated</span>'
        if msg.get("used_memory"):
            badges += '<span class="badge-memory">memory</span>'

        st.markdown(
            f'<div class="msg-assistant">{msg["content"]}{badges}</div>',
            unsafe_allow_html=True,
        )

        # ── Show chunks / sources ──
        if show_chunks and msg.get("chunks"):
            with st.expander(f"{len(msg['chunks'])} source chunks retrieved", expanded=False):
                for i, chunk in enumerate(msg["chunks"], 1):
                    if isinstance(chunk, dict):
                        score   = chunk.get("@search.reranker_score") or chunk.get("_score_rrf") or chunk.get("score")
                        snippet = chunk.get("cleaned_text") or chunk.get("chunk_text") or ""
                        section = chunk.get("section") or ""
                        page    = chunk.get("page") or ""
                        source  = chunk.get("source") or ""
                    else:
                        score   = getattr(chunk, "reranker_score", None) or getattr(chunk, "score", None)
                        snippet = getattr(chunk, "cleaned_text", "") or getattr(chunk, "chunk_text", "")
                        section = getattr(chunk, "section", "") or ""
                        page    = getattr(chunk, "page", "")
                        source  = getattr(chunk, "source", "")
                    score_html = f'<span class="score-badge">score {float(score):.4f}</span>' if score else ""
                    snippet = snippet[:220].replace("<", "&lt;").replace(">", "&gt;")
                    st.markdown(f"""
                    <div class="citation-card">
                      <div class="src">[{i}] {source} {score_html}</div>
                      <div class="meta">{section}{"  &middot;  Page " + str(page) if page else ""}</div>
                      <div class="snippet">"{snippet}..."</div>
                    </div>
                    """, unsafe_allow_html=True)

        # ── Show web sources ──
        if show_chunks and msg.get("web_sources"):
            with st.expander(f"{len(msg['web_sources'])} web sources retrieved", expanded=False):
                for i, src in enumerate(msg["web_sources"], 1):
                    title   = src.get("title", "")
                    url     = src.get("url", "")
                    name    = src.get("source_name", "")
                    snippet = src.get("content", "")[:250].replace("<", "&lt;").replace(">", "&gt;")
                    st.markdown(f"""
                    <div class="source-card">
                      <div class="src-name">[{i}] {name} — {title}</div>
                      <div class="src-url"><a href="{url}" target="_blank">{url[:70]}</a></div>
                      <div class="src-snippet">"{snippet}..."</div>
                    </div>
                    """, unsafe_allow_html=True)


# ── Chat input ────────────────────────────────────────────────────────
question = st.chat_input("Ask a question about your documents...")

if question and question.strip():
    st.session_state.messages.append({"role": "user", "content": question})

    with st.spinner(f"Searching with {rag_mode}..."):
        t0 = time.time()
        try:
            from naive_rag.retriever import rewrite_followup

            # ── Conversation memory: rewrite follow-ups ────────────
            history = []
            if memory_window > 0:
                history = st.session_state.messages[-(memory_window * 2):]

            rewrite_result = rewrite_followup(question, history)
            effective_q    = rewrite_result["rewritten"]
            is_followup    = rewrite_result["is_followup"]
            used_memory    = rewrite_result["used_memory"] and bool(history)

            answer       = ""
            chunks       = []
            web_sources  = []
            sources_list = []
            avg_score    = 0

            # ════════════════════════════════════════════════════════
            #  NAIVE RAG
            # ════════════════════════════════════════════════════════
            if rag_mode == "Naive RAG":
                naive = load_naive_rag()
                if "error" in naive:
                    raise RuntimeError(naive["error"])

                result = naive["retriever"].ask(effective_q, top_k=top_k, verbose=False)
                answer = result["answer"]
                chunks = result["chunks"]
                sources_list = list({c.get("source", "") for c in chunks if c.get("source")})

                scores_vals = []
                for c in chunks:
                    s = (c.get("@search.reranker_score")
                         or c.get("_score_rrf")
                         or c.get("_score_vector")
                         or c.get("_score_fulltext")
                         or 0)
                    try:
                        scores_vals.append(float(s))
                    except (ValueError, TypeError):
                        pass
                avg_score = sum(scores_vals) / len(scores_vals) if scores_vals else 0

            # ════════════════════════════════════════════════════════
            #  GRAPH RAG
            # ════════════════════════════════════════════════════════
            elif rag_mode == "Graph RAG":
                graph = load_graph_rag()
                if "error" in graph:
                    raise RuntimeError(graph["error"])

                retriever = graph["retriever"]
                subgraph  = retriever.retrieve(effective_q, top_k=top_k)
                nodes     = subgraph.get("nodes", [])
                edges     = subgraph.get("edges", [])

                # Generate answer using the retriever's ask method
                answer = retriever.ask(effective_q, top_k=top_k)

                # Convert nodes to chunk-like dicts for display
                chunks = [
                    {
                        "source":      n.get("source", ""),
                        "chunk_text":  "%s: %s" % (n.get("name", ""), n.get("description", "")),
                        "cleaned_text":"%s: %s" % (n.get("name", ""), n.get("description", "")),
                        "page":        n.get("page", 0),
                        "section":     n.get("name", ""),
                    }
                    for n in nodes
                ]
                sources_list = list({n.get("source", "") for n in nodes if n.get("source")})

                # Graph RAG: use real entity match scores from graph search
                match_scores = [n.get("_match_score", 0) for n in nodes if n.get("_match_score", 0) > 0]
                if match_scores:
                    avg_score = sum(match_scores) / len(match_scores)
                elif nodes:
                    avg_score = min(len(nodes) / top_k, 1.0)

            # ════════════════════════════════════════════════════════
            #  HYBRID RAG
            # ════════════════════════════════════════════════════════
            elif rag_mode == "Hybrid RAG":
                hybrid = load_hybrid_rag()
                if "error" in hybrid:
                    raise RuntimeError(hybrid["error"])

                retriever = hybrid["retriever"]

                # Capture printed output as the answer
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    result = retriever.ask(effective_q)
                raw_output = buf.getvalue().strip()

                # Prefer returned string over stdout capture
                if isinstance(result, str) and len(result) > 20:
                    answer = result
                else:
                    answer = raw_output

                # Clean terminal formatting lines
                clean_lines = []
                for ln in answer.split("\n"):
                    s = ln.strip()
                    if s.startswith("=") or s.startswith("──") or s.startswith("? "):
                        continue
                    clean_lines.append(ln)
                answer = "\n".join(clean_lines).strip()

                # Try to get chunks from both sources
                try:
                    subgraph = retriever.graph.retrieve(effective_q, top_k=top_k)
                    graph_chunks = [
                        {
                            "source":       n.get("source", ""),
                            "cleaned_text": "%s: %s" % (n.get("name",""), n.get("description","")),
                            "page":         n.get("page", 0),
                            "section":      n.get("name", ""),
                            "_match_score": n.get("_match_score", 0),
                        }
                        for n in subgraph.get("nodes", [])
                    ]
                except Exception:
                    graph_chunks = []

                try:
                    naive_chunks = retriever.naive.retrieve(effective_q, top_k=top_k) if retriever.naive else []
                except Exception:
                    naive_chunks = []

                chunks = (graph_chunks + (naive_chunks if isinstance(naive_chunks, list) else []))[:top_k]
                sources_list = list({c.get("source", "") for c in chunks if c.get("source")})

                # Compute score: naive chunks have search scores, graph chunks don't
                naive_scores = []
                for c in (naive_chunks if isinstance(naive_chunks, list) else []):
                    if isinstance(c, dict):
                        s = (c.get("@search.reranker_score")
                             or c.get("_score_rrf")
                             or c.get("_score_vector")
                             or c.get("_score_fulltext")
                             or 0)
                    else:
                        s = 0
                    try:
                        v = float(s)
                        if v > 0:
                            naive_scores.append(v)
                    except (ValueError, TypeError):
                        pass
                # Graph score: use real match scores if available, else count-proxy
                g_match = [c.get("_match_score", 0) for c in graph_chunks if c.get("_match_score", 0) > 0]
                graph_score = sum(g_match) / len(g_match) if g_match else (
                    min(len(graph_chunks) / max(top_k, 1), 1.0) if graph_chunks else 0
                )
                naive_score = sum(naive_scores) / len(naive_scores) if naive_scores else 0
                # Blend: if both exist average them, otherwise use whichever is available
                if graph_score > 0 and naive_score > 0:
                    avg_score = (graph_score + naive_score) / 2
                else:
                    avg_score = graph_score or naive_score or 0

            # ════════════════════════════════════════════════════════
            #  WEB RESEARCH
            # ════════════════════════════════════════════════════════
            elif rag_mode == "Web Research":
                agent_res = load_web_agent()
                if "error" in agent_res:
                    raise RuntimeError(agent_res["error"])

                result = agent_res["agent"].search_and_answer(effective_q)
                answer = result["answer"]
                web_sources = [
                    {
                        "title":       s.title,
                        "url":         s.url,
                        "source_name": s.source_name,
                        "content":     s.content,
                        "category":    s.category,
                        "trust":       s.trust,
                    }
                    for s in result.get("sources", [])
                ]
                sources_list = [s["source_name"] for s in web_sources]

                # Web: use average trust level (1-5) normalized to 0-1
                if web_sources:
                    avg_score = sum(s.get("trust", 0) for s in web_sources) / (len(web_sources) * 5)

            elapsed = time.time() - t0

            # ── Auto-evaluate answer quality ──────────────────
            context_text = ""
            for c in chunks[:5]:
                context_text += (c.get("cleaned_text") or c.get("chunk_text") or "") + "\n"
            for ws in web_sources[:3]:
                context_text += (ws.get("content", "") or "")[:500] + "\n"
            eval_scores = _evaluate_answer(effective_q, context_text, answer)

            # ── Log entry ──────────────────────────────────────
            _append_log({
                "question":      question,
                "effective_q":   effective_q if is_followup else question,
                "timestamp":     datetime.now().isoformat(timespec="seconds"),
                "mode":          rag_mode,
                "response_time": round(elapsed, 2),
                "num_chunks":    len(chunks) + len(web_sources),
                "avg_score":     round(avg_score, 4),
                "answer_length": len(answer),
                "reformulated":  is_followup,
                "used_memory":   used_memory,
                "sources":       sources_list,
                "groundedness":  eval_scores["groundedness"],
                "relevancy":     eval_scores["relevancy"],
                "completeness":  eval_scores["completeness"],
                "hallucination": eval_scores["hallucination"],
            })

            # ── Chat log entry ────────────────────────────────
            _append_chat({
                "timestamp":    datetime.now().isoformat(timespec="seconds"),
                "mode":         rag_mode,
                "question":     question,
                "effective_q":  effective_q if is_followup else question,
                "answer":       answer,
                "sources":      sources_list,
                "is_followup":  is_followup,
                "used_memory":  used_memory,
                "response_time": round(elapsed, 2),
            })

            st.session_state.messages.append({
                "role":         "assistant",
                "content":      answer,
                "chunks":       chunks,
                "web_sources":  web_sources,
                "rag_mode":     rag_mode,
                "reformulated": is_followup,
                "used_memory":  used_memory,
            })

            # Auto-save conversation to persistent storage
            _save_current_session()

        except Exception as e:
            st.session_state.messages.append({
                "role":    "assistant",
                "content": f"Error: {str(e)}",
                "chunks":  [],
                "rag_mode": rag_mode,
            })

    st.rerun()

# ── Empty state ────────────────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown("""
    <div style="text-align:center; color:#94A3B8; margin-top:60px;">
      <div style="font-size:16px; font-weight:600; color:#475569;">Ask anything about your documents</div>
      <div style="font-size:13px; margin-top:6px;">
        Select a RAG mode in the sidebar and start asking questions.<br>
        <b>Naive RAG</b> — vector/fulltext/hybrid search over document chunks<br>
        <b>Graph RAG</b> — knowledge graph entity traversal<br>
        <b>Hybrid RAG</b> — graph + naive combined with smart fallback<br>
        <b>Web Research</b> — live search across trusted publishers
      </div>
    </div>
    """, unsafe_allow_html=True)
