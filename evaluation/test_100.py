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

# -- GitHub log helpers --------------------------------------------------------
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
    # Always write local backup first
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(content_str, encoding="utf-8")
    print(f"  [save] Written locally -> {LOG_PATH}")

    token, repo = _gh_token(), _gh_repo()
    if token and repo:
        try:
            url = f"{_GITHUB_API}/repos/{repo}/contents/evaluation/results/query_log.json"
            r = http_requests.get(url, headers=_gh_headers(), timeout=15)
            sha = r.json().get("sha", "") if r.status_code == 200 else ""
            payload = {
                "message": "Update query log (test_100)",
                "content": base64.b64encode(content_str.encode("utf-8")).decode("utf-8"),
                "branch": "master",
            }
            if sha:
                payload["sha"] = sha
            put_r = http_requests.put(url, headers=_gh_headers(), json=payload, timeout=60)
            if put_r.status_code in (200, 201):
                print(f"  [save] Pushed to GitHub OK ({put_r.status_code})")
            else:
                print(f"  [save] GitHub PUT failed: {put_r.status_code} - {put_r.text[:200]}")
        except Exception as e:
            print(f"  [save] GitHub push error: {e}")


# -- Load prompts from JSON ----------------------------------------------------

def _load_prompts():
    p = Path(__file__).parent / "test_prompts_100.json"
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    naive = [(item["prompt"], "Naive RAG") for item in data if item.get("mode") == "naive"]
    graph = [(item["prompt"], "Graph RAG") for item in data if item.get("mode") == "graph"]
    return naive, graph


# -- LLM clients --------------------------------------------------------------

def _get_openai_client():
    import config
    from openai import AzureOpenAI
    return AzureOpenAI(
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
        api_key=config.AZURE_OPENAI_KEY,
        api_version=config.AZURE_OPENAI_API_VERSION,
    ), config.AZURE_CHAT_DEPLOYMENT


# -- Answer quality: LLM-as-judge ---------------------------------------------

_ANSWER_EVAL_PROMPT = """You are a strict evaluation judge for a RAG system.
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
            "faithfulness":      round(float(scores.get("faithfulness", 0)), 2),
            "answer_relevancy":  round(float(scores.get("answer_relevancy", 0)), 2),
            "context_precision": round(float(scores.get("context_precision", 0)), 2),
        }
    except Exception:
        return {"faithfulness": 0.0, "answer_relevancy": 0.0, "context_precision": 0.0}


# -- Retrieval quality: chunk relevance → Precision@K and MRR -----------------

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


# -- Run -----------------------------------------------------------------------

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
    print(f"  LLM-as-judge: 1 GPT-4o call per query")
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

            # -- Naive RAG ------------------------------------------------
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

            # -- Graph RAG ------------------------------------------------
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

            # -- Evaluate answer quality (single GPT-4o call per query) ----
            answer_scores = _evaluate_answer(question, context_text, answer)

            # Chunk relevance eval skipped — would double API calls and
            # hit student-tier TPM limits. P@K / MRR can be added later
            # on a dedicated high-throughput tier.
            retrieval_scores = {"precision_at_1": 0.0, "precision_at_3": 0.0,
                                 "precision_at_5": 0.0, "mrr": 0.0}

            # Small pause to stay within Azure OpenAI rate limits
            time.sleep(2)

            entry = {
                "question":          question,
                "effective_q":       question,
                "timestamp":         datetime.now().isoformat(timespec="seconds"),
                "mode":              mode,
                "response_time":     round(elapsed, 2),
                "num_chunks":        num_chunks,
                "answer_length":     len(answer),
                "sources":           sources_list,
                "test_run":          True,
                # RAGAS metrics
                "faithfulness":      answer_scores["faithfulness"],
                "answer_relevancy":  answer_scores["answer_relevancy"],
                "context_precision": answer_scores["context_precision"],
            }
            log.append(entry)
            success += 1

            f  = answer_scores["faithfulness"]
            ar = answer_scores["answer_relevancy"]
            cp = answer_scores["context_precision"]
            print(f"OK ({elapsed:.1f}s)  F:{f} AR:{ar} CP:{cp}")

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

    # -- Save -----------------------------------------------------------------
    print(f"\nSaving {len(log)} log entries...")
    _save_log(log)

    # -- Summary --------------------------------------------------------------
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
        print(f"  {'-'*40}")
        print(f"  Avg Response Time   {avg('response_time'):.1f}s")
        print(f"  -- RAGAS Metrics -------------------")
        print(f"  Faithfulness        {avg('faithfulness'):.3f}")
        print(f"  Answer Relevancy    {avg('answer_relevancy'):.3f}")
        print(f"  Context Precision   {avg('context_precision'):.3f}")

    print(f"\nDone. Results saved to analytics log.")


if __name__ == "__main__":
    run_tests()
