"""
test_100.py — Run 100 test prompts across Naive RAG and Graph RAG.

Metrics per query (all via LLM-as-judge):
  Answer quality : groundedness, relevancy, completeness, hallucination
  Retrieval      : precision@1, precision@3, precision@5, MRR

Prompts are loaded from evaluation/test_prompts_100.json.
  id  1-50  → Naive RAG
  id 51-100 → Graph RAG

Usage:
    python evaluation/test_100.py
    python evaluation/test_100.py --clear   # wipe old test entries first
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import json
import time
import base64
import os
import re
import requests as http_requests
from datetime import datetime

# ── GitHub log helpers ────────────────────────────────────────────────────────
_GITHUB_API = "https://api.github.com"


def _gh_token():
    try:
        import streamlit as st
        return st.secrets.get("GITHUB_TOKEN", os.getenv("GITHUB_TOKEN", ""))
    except Exception:
        return os.getenv("GITHUB_TOKEN", "")


def _gh_repo():
    try:
        import streamlit as st
        return st.secrets.get("GITHUB_REPO", os.getenv("GITHUB_REPO", ""))
    except Exception:
        return os.getenv("GITHUB_REPO", "")


def _gh_headers():
    return {
        "Authorization": f"token {_gh_token()}",
        "Accept": "application/vnd.github.v3+json",
    }


LOG_PATH = Path(__file__).parent / "results" / "query_log.json"


def _load_log():
    token, repo = _gh_token(), _gh_repo()
    if token and repo:
        try:
            url = f"{_GITHUB_API}/repos/{repo}/contents/evaluation/results/query_log.json"
            r = http_requests.get(url, headers=_gh_headers(), timeout=10)
            if r.status_code == 200:
                content = base64.b64decode(r.json()["content"]).decode("utf-8")
                return json.loads(content)
        except Exception:
            pass
    if LOG_PATH.exists():
        try:
            return json.loads(LOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_log(log):
    content_str = json.dumps(log, indent=2, ensure_ascii=False)
    token, repo = _gh_token(), _gh_repo()
    if token and repo:
        try:
            url = f"{_GITHUB_API}/repos/{repo}/contents/evaluation/results/query_log.json"
            r = http_requests.get(url, headers=_gh_headers(), timeout=10)
            sha = r.json().get("sha", "") if r.status_code == 200 else ""
            payload = {
                "message": "Update query log (test_100)",
                "content": base64.b64encode(content_str.encode("utf-8")).decode("utf-8"),
                "branch": "master",
            }
            if sha:
                payload["sha"] = sha
            http_requests.put(url, headers=_gh_headers(), json=payload, timeout=10)
            return
        except Exception:
            pass
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(content_str, encoding="utf-8")


# ── Load prompts from JSON ────────────────────────────────────────────────────

def _load_prompts():
    p = Path(__file__).parent / "test_prompts_100.json"
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    naive = [(item["prompt"], "Naive RAG") for item in data if item.get("mode") == "naive"]
    graph = [(item["prompt"], "Graph RAG") for item in data if item.get("mode") == "graph"]
    return naive, graph


# ── LLM clients ──────────────────────────────────────────────────────────────

def _get_openai_client():
    import config
    from openai import AzureOpenAI
    return AzureOpenAI(
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
        api_key=config.AZURE_OPENAI_KEY,
        api_version=config.AZURE_OPENAI_API_VERSION,
    ), config.AZURE_CHAT_DEPLOYMENT


# ── Answer quality: LLM-as-judge ─────────────────────────────────────────────

_ANSWER_EVAL_PROMPT = """You are a strict evaluation judge for a RAG system.
Given a QUESTION, CONTEXT (retrieved documents), and ANSWER, score on 4 metrics (0.0–1.0).

QUESTION: {question}

CONTEXT:
{context}

ANSWER:
{answer}

Rubrics:
- groundedness: Does the answer use information from the context? (1.0 = all from context, 0.0 = ignores context)
- relevancy: Does the answer address the question? (1.0 = fully, 0.0 = off-topic)
- completeness: Does the answer cover the key info in context relevant to the question? (1.0 = thorough, 0.0 = misses everything)
- hallucination: Is the answer free from info NOT in context? (1.0 = every claim traceable, 0.0 = heavily fabricated)

Return ONLY valid JSON: {{"groundedness": X, "relevancy": X, "completeness": X, "hallucination": X}}"""


def _evaluate_answer(question: str, context: str, answer: str) -> dict:
    try:
        client, model = _get_openai_client()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _ANSWER_EVAL_PROMPT.format(
                question=question[:500],
                context=context[:8000],
                answer=answer[:3000],
            )}],
            temperature=0.0,
            max_tokens=150,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        scores = json.loads(raw)
        return {
            "groundedness":  round(float(scores.get("groundedness", 0)), 2),
            "relevancy":     round(float(scores.get("relevancy", 0)), 2),
            "completeness":  round(float(scores.get("completeness", 0)), 2),
            "hallucination": round(float(scores.get("hallucination", 0)), 2),
        }
    except Exception:
        return {"groundedness": 0.0, "relevancy": 0.0, "completeness": 0.0, "hallucination": 0.0}


# ── Retrieval quality: chunk relevance → Precision@K and MRR ─────────────────

_CHUNK_EVAL_PROMPT = """You are evaluating retrieval quality for a RAG system.
Given a QUESTION and a list of retrieved CHUNKS, decide whether each chunk is relevant to answering the question.

QUESTION: {question}

CHUNKS:
{chunks}

For each chunk index (0-based), return true if it is relevant to the question, false otherwise.
Return ONLY a JSON array of booleans with exactly {n} elements, e.g. [true, false, true, true, false]"""


def _evaluate_chunks(question: str, chunks: list[str]) -> dict:
    """Score retrieved chunks for relevance. Returns precision@1/3/5 and MRR."""
    if not chunks:
        return {"precision_at_1": 0.0, "precision_at_3": 0.0, "precision_at_5": 0.0, "mrr": 0.0}

    k = min(5, len(chunks))
    chunks_text = "\n\n".join(
        f"[{i}] {c[:400]}" for i, c in enumerate(chunks[:k])
    )
    try:
        client, model = _get_openai_client()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _CHUNK_EVAL_PROMPT.format(
                question=question[:500],
                chunks=chunks_text,
                n=k,
            )}],
            temperature=0.0,
            max_tokens=50,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        relevance = json.loads(raw)
        if not isinstance(relevance, list):
            raise ValueError("not a list")
        # Pad to 5 with False if fewer chunks returned
        while len(relevance) < 5:
            relevance.append(False)
        relevance = [bool(v) for v in relevance[:5]]
    except Exception:
        relevance = [False] * 5

    def p_at(k_):
        return round(sum(relevance[:k_]) / k_, 2) if k_ > 0 else 0.0

    mrr = 0.0
    for rank, rel in enumerate(relevance, 1):
        if rel:
            mrr = round(1.0 / rank, 2)
            break

    return {
        "precision_at_1": p_at(1),
        "precision_at_3": p_at(min(3, len(chunks))),
        "precision_at_5": p_at(min(5, len(chunks))),
        "mrr":            mrr,
    }


# ── Run ───────────────────────────────────────────────────────────────────────

def run_tests():
    import asyncio
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    naive_prompts, graph_prompts = _load_prompts()
    all_tests = naive_prompts + graph_prompts

    # Clear old test entries if --clear flag
    if "--clear" in sys.argv:
        print("Clearing old test entries from log...")
        old_log = _load_log()
        kept = [e for e in old_log if not e.get("test_run")]
        _save_log(kept)
        print(f"  Kept {len(kept)} non-test entries.")

    print(f"\n{'='*65}")
    print(f"  ConsultantIQ — 100 Prompt Evaluation")
    print(f"  Naive RAG: {len(naive_prompts)} prompts | Graph RAG: {len(graph_prompts)} prompts")
    print(f"  Metrics: groundedness · relevancy · completeness · hallucination")
    print(f"           precision@1/3/5 · MRR  (all via LLM-as-judge)")
    print(f"{'='*65}\n")

    print("Loading Naive RAG...")
    from naive_rag.retriever import RAGRetriever
    naive = RAGRetriever()

    print("Loading Graph RAG...")
    from graph_rag.retriever_graph import GraphRetriever
    graph = GraphRetriever()

    log = _load_log()
    success, errors = 0, 0

    for i, (question, mode) in enumerate(all_tests, 1):
        label = f"[{i:3d}/{len(all_tests)}] ({mode:10s}) {question[:50]}..."
        print(label, end=" ", flush=True)

        t0 = time.time()
        try:
            context_text = ""
            chunk_texts  = []

            # ── Naive RAG ────────────────────────────────────────────────
            if mode == "Naive RAG":
                result = naive.ask(question, top_k=5, verbose=False)
                answer = result["answer"]
                chunks = result["chunks"]
                sources_list = list({c.get("source", "") for c in chunks if c.get("source")})
                scores_vals  = []
                for c in chunks:
                    s = (c.get("@search.reranker_score") or c.get("_score_rrf")
                         or c.get("_score_vector") or c.get("_score_fulltext") or 0)
                    try:
                        scores_vals.append(float(s))
                    except (ValueError, TypeError):
                        pass
                avg_score    = sum(scores_vals) / len(scores_vals) if scores_vals else 0.0
                num_chunks   = len(chunks)
                chunk_texts  = [(c.get("cleaned_text") or c.get("chunk_text") or "") for c in chunks[:5]]
                context_text = "\n".join(chunk_texts)

            # ── Graph RAG ────────────────────────────────────────────────
            elif mode == "Graph RAG":
                import io, contextlib
                subgraph   = graph.retrieve(question, top_k=5)
                nodes      = subgraph.get("nodes", [])
                graph_edges = subgraph.get("edges", [])
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    answer = graph.ask(question, top_k=5)
                sources_list = list({n.get("source", "") for n in nodes if n.get("source")})
                match_scores = [n.get("_match_score", 0) for n in nodes if n.get("_match_score", 0) > 0]
                avg_score    = sum(match_scores) / len(match_scores) if match_scores else (
                    min(len(nodes) / 5, 1.0) if nodes else 0.0
                )
                num_chunks   = len(nodes)
                chunk_texts  = [f"{n.get('name','')}: {n.get('description','')}" for n in nodes]
                context_text = "\n".join(chunk_texts)
                for e in graph_edges:
                    context_text += f"\n{e.get('from','')} {e.get('type','')} {e.get('to','')}"

            elapsed = time.time() - t0

            # ── Evaluate answer quality ───────────────────────────────────
            answer_scores = _evaluate_answer(question, context_text, answer)

            # ── Evaluate retrieval quality ────────────────────────────────
            retrieval_scores = _evaluate_chunks(question, chunk_texts)

            entry = {
                "question":        question,
                "effective_q":     question,
                "timestamp":       datetime.now().isoformat(timespec="seconds"),
                "mode":            mode,
                "response_time":   round(elapsed, 2),
                "num_chunks":      num_chunks,
                "avg_score":       round(avg_score, 4),
                "answer_length":   len(answer),
                "reformulated":    False,
                "used_memory":     False,
                "sources":         sources_list,
                "test_run":        True,
                # Answer quality
                "groundedness":    answer_scores["groundedness"],
                "relevancy":       answer_scores["relevancy"],
                "completeness":    answer_scores["completeness"],
                "hallucination":   answer_scores["hallucination"],
                # Retrieval quality
                "precision_at_1":  retrieval_scores["precision_at_1"],
                "precision_at_3":  retrieval_scores["precision_at_3"],
                "precision_at_5":  retrieval_scores["precision_at_5"],
                "mrr":             retrieval_scores["mrr"],
            }
            log.append(entry)
            success += 1

            g  = answer_scores["groundedness"]
            r  = answer_scores["relevancy"]
            c  = answer_scores["completeness"]
            h  = answer_scores["hallucination"]
            p1 = retrieval_scores["precision_at_1"]
            p5 = retrieval_scores["precision_at_5"]
            m  = retrieval_scores["mrr"]
            print(f"OK ({elapsed:.1f}s)  G:{g} R:{r} C:{c} H:{h}  P@1:{p1} P@5:{p5} MRR:{m}")

        except Exception as e:
            elapsed = time.time() - t0
            errors += 1
            print(f"ERR ({elapsed:.1f}s) — {str(e)[:60]}")
            log.append({
                "question": question, "effective_q": question,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "mode": mode, "response_time": round(elapsed, 2),
                "num_chunks": 0, "avg_score": 0, "answer_length": 0,
                "reformulated": False, "used_memory": False, "sources": [],
                "test_run": True, "error": str(e)[:200],
                "groundedness": 0.0, "relevancy": 0.0,
                "completeness": 0.0, "hallucination": 0.0,
                "precision_at_1": 0.0, "precision_at_3": 0.0,
                "precision_at_5": 0.0, "mrr": 0.0,
            })

    # ── Save ─────────────────────────────────────────────────────────────────
    print(f"\nSaving {len(log)} log entries...")
    _save_log(log)

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  RESULTS  —  Success: {success}  |  Errors: {errors}  |  Total: {len(all_tests)}")
    print(f"{'='*65}")

    test_entries = [e for e in log if e.get("test_run") and not e.get("error")]
    for mode in ["Naive RAG", "Graph RAG"]:
        me = [e for e in test_entries if e.get("mode") == mode]
        if not me:
            continue
        n = len(me)
        def avg(key): return round(sum(e.get(key, 0) for e in me) / n, 3)
        print(f"\n  {mode}  ({n} queries)")
        print(f"  {'─'*40}")
        print(f"  Avg Response Time   {avg('response_time'):.1f}s")
        print(f"  ── Answer Quality ──────────────────")
        print(f"  Groundedness        {avg('groundedness'):.3f}")
        print(f"  Relevancy           {avg('relevancy'):.3f}")
        print(f"  Completeness        {avg('completeness'):.3f}")
        print(f"  Hallucination-free  {avg('hallucination'):.3f}")
        print(f"  ── Retrieval Quality ───────────────")
        print(f"  Precision@1         {avg('precision_at_1'):.3f}")
        print(f"  Precision@3         {avg('precision_at_3'):.3f}")
        print(f"  Precision@5         {avg('precision_at_5'):.3f}")
        print(f"  MRR                 {avg('mrr'):.3f}")

    print(f"\nDone. Results saved to analytics log.")


if __name__ == "__main__":
    run_tests()
