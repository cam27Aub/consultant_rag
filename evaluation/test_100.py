"""
test_100.py — Run 100 test prompts across Naive, Graph, and Hybrid RAG.
Results are saved to the app's analytics log (GitHub-backed).

Usage:
    python evaluation/test_100.py
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
import requests as http_requests
from datetime import datetime

# ── GitHub log helpers (same as app.py) ───────────────────────────────
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


# ── 100 Test Prompts ──────────────────────────────────────────────────
# Divided: 34 Naive, 33 Graph, 33 Hybrid

NAIVE_PROMPTS = [
    # Strategic Frameworks (strategic_frameworks_guide.docx)
    "What are Porter's Five Forces?",
    "Explain the BCG Growth-Share Matrix quadrants.",
    "What is the MECE principle?",
    "What are the primary activities in Porter's Value Chain?",
    "What are the support activities in the Value Chain?",
    "How do you apply Porter's Five Forces to an industry?",
    "What is competitive rivalry in Porter's framework?",
    "Define threat of new entrants.",
    "How does bargaining power of buyers affect pricing?",
    "What characterizes a 'Star' in the BCG Matrix?",
    "When should a company divest a 'Dog' business unit?",
    "How does the MECE principle help with issue trees?",
    # Digital Transformation (digital_transformation_playbook.pdf)
    "What are the four pillars of digital transformation?",
    "Why do digital transformation programs fail?",
    "How should a digital transformation roadmap be designed?",
    "What percentage of digital transformations fail?",
    "What role does executive sponsorship play in digital transformation?",
    "How much budget should be allocated to change management?",
    "What is the role of quick wins in a transformation roadmap?",
    "How many initiatives should a transformation portfolio include?",
    # Financial Analysis (financial_analysis_toolkit.pdf)
    "What is EBITDA and why is it useful?",
    "What are the three valuation methodologies in consulting?",
    "What is Discounted Cash Flow analysis?",
    "Explain comparable company analysis.",
    "What are precedent transactions?",
    "What financial modeling best practices should consultants follow?",
    "Why should inputs be separated from calculations in a model?",
    "What color coding conventions are used in financial models?",
    "What scenarios should a financial model include?",
    # Client Engagement (client_engagement_best_practices.docx)
    "What is the pyramid principle in consulting?",
    "Who developed the pyramid principle?",
    "How should stakeholders be managed during an engagement?",
    "What types of stakeholders exist in a consulting engagement?",
    "How should you handle potential blockers in a project?",
]

GRAPH_PROMPTS = [
    # Entity/relationship focused questions
    "How does Porter's Five Forces relate to competitive strategy?",
    "What is the relationship between BCG Matrix and portfolio management?",
    "How are MECE and issue trees connected?",
    "What connects digital transformation to customer experience?",
    "How does EBITDA relate to company valuation?",
    "What is the link between DCF analysis and cash flow forecasting?",
    "How does the pyramid principle connect to McKinsey?",
    "What entities are involved in stakeholder management?",
    "How do the four pillars of digital transformation interact?",
    "What is the relationship between operational efficiency and technology?",
    "How does change management relate to digital transformation success?",
    "What connects competitive rivalry to market share?",
    "How do support activities in the value chain enable primary activities?",
    "What is the relationship between governance and program success?",
    "How does bargaining power relate to supply chain management?",
    "What frameworks are used for industry analysis?",
    "How does business model innovation connect to digital strategy?",
    "What metrics are used to measure consulting engagement success?",
    "How do financial metrics relate to strategic decision-making?",
    "What connects client engagement to project delivery?",
    "How does data analytics support business transformation?",
    "What is the relationship between talent gaps and transformation failure?",
    "How do trading multiples compare to DCF in valuation?",
    "What connects executive sponsorship to change management?",
    "How does scenario analysis relate to financial modeling?",
    "What entities are part of the value chain framework?",
    "How do exit barriers affect competitive rivalry?",
    "What links switching costs to buyer bargaining power?",
    "How does product differentiation relate to competitive advantage?",
    "What connects inbound logistics to operations in the value chain?",
    "How are consulting frameworks interconnected?",
    "What is the relationship between risk assessment and financial analysis?",
    "How does market growth rate relate to the BCG Matrix?",
]

HYBRID_PROMPTS = [
    # Complex analytical questions needing both context types
    "Compare Porter's Five Forces with the BCG Matrix for strategic planning.",
    "How can digital transformation principles be applied using consulting frameworks?",
    "Explain the complete process of industry analysis using available frameworks.",
    "What financial tools and strategic frameworks should be used together for M&A analysis?",
    "How do the pyramid principle and stakeholder management work together in client engagements?",
    "Compare DCF analysis with comparable company analysis for valuation.",
    "How should a consultant approach a digital transformation engagement from start to finish?",
    "What are all the frameworks available for competitive analysis and how do they differ?",
    "How can financial modeling best practices support strategic decision-making?",
    "Explain the relationship between change management and digital transformation success with specific examples.",
    "What is the complete stakeholder management process and how does it relate to the pyramid principle?",
    "How should value chain analysis inform digital transformation strategy?",
    "Compare all three valuation methodologies and when to use each.",
    "What are the key success factors for consulting engagements across all document sources?",
    "How do strategic frameworks help in assessing market attractiveness?",
    "Explain how EBITDA analysis can be used alongside strategic frameworks for business evaluation.",
    "What is the role of governance in both digital transformation and financial modeling?",
    "How can the MECE principle be applied to structure a digital transformation assessment?",
    "What are the common themes across strategic frameworks and financial analysis tools?",
    "How should a consultant structure a competitive analysis presentation?",
    "Compare the failure factors of digital transformation with stakeholder management challenges.",
    "What is the comprehensive approach to evaluating a company's competitive position?",
    "How do quick wins in digital transformation relate to the BCG Matrix's prioritization?",
    "Explain how all four documents' concepts connect to form a consulting toolkit.",
    "What analytical frameworks help in understanding industry dynamics?",
    "How should scenario analysis in financial models align with strategic planning?",
    "What is the relationship between market forces and digital disruption?",
    "How can value chain analysis be used to identify digital transformation opportunities?",
    "Compare the role of data analytics across strategic, financial, and transformation contexts.",
    "What best practices from all sources apply to a new market entry analysis?",
    "How does the pyramid principle help present financial analysis findings?",
    "What is the integrated approach to assessing business unit performance?",
    "How do consulting frameworks address uncertainty in strategic planning?",
]

ALL_TESTS = (
    [(q, "Naive RAG") for q in NAIVE_PROMPTS] +
    [(q, "Graph RAG") for q in GRAPH_PROMPTS] +
    [(q, "Hybrid RAG") for q in HYBRID_PROMPTS]
)


def _evaluate_answer(question, context, answer):
    """Fast local evaluation — same as app.py. No LLM calls."""
    import re as _re
    import math as _math

    def _tok(text):
        return [w for w in _re.findall(r'[a-z]{3,}', text.lower())]

    def _cos(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        na = _math.sqrt(sum(x * x for x in a))
        nb = _math.sqrt(sum(x * x for x in b))
        return dot / (na * nb) if na > 0 and nb > 0 else 0.0

    def _rouge_l(ref, hyp):
        rw = _tok(ref)[:500]
        hw = _tok(hyp)[:500]
        if not rw or not hw:
            return 0.0, 0.0
        m, n = len(rw), len(hw)
        prev = [0] * (n + 1)
        for i in range(1, m + 1):
            curr = [0] * (n + 1)
            for j in range(1, n + 1):
                if rw[i - 1] == hw[j - 1]:
                    curr[j] = prev[j - 1] + 1
                else:
                    curr[j] = max(curr[j - 1], prev[j])
            prev = curr
        lcs = prev[n]
        return (lcs / n if n else 0.0), (lcs / m if m else 0.0)

    def _kw_recall(ctx, ans):
        stops = {"the","and","for","are","with","that","this","from","have","has",
                 "been","was","were","will","can","which","their","they","also",
                 "more","than","into","such","each","about","between","should",
                 "these","other","not","but","its","all","any","our","your"}
        cw = set(_tok(ctx)) - stops
        aw = set(_tok(ans))
        return len(cw & aw) / len(cw) if cw else 0.0

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
        va = resp.data[0].embedding
        vc = resp.data[1].embedding
        vq = resp.data[2].embedding
        embed_ground = _cos(va, vc)
        embed_relev = _cos(va, vq)
    except Exception:
        embed_ground = 0.0
        embed_relev = 0.0

    rp, rr = _rouge_l(context, answer)
    kw = _kw_recall(context, answer)

    return {
        "groundedness":  round(embed_ground, 2),
        "relevancy":     round(embed_relev, 2),
        "completeness":  round(0.5 * kw + 0.5 * rr, 2),
        "hallucination": round(rp, 2),
    }


def run_tests():
    import asyncio
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Clear old test entries if --clear flag
    clear_old = "--clear" in sys.argv
    if clear_old:
        print("Clearing old test entries from log...")
        old_log = _load_log()
        old_log = [e for e in old_log if not e.get("test_run")]
        _save_log(old_log)
        print(f"  Kept {len(old_log)} non-test entries.")

    print(f"\n{'='*60}")
    print(f"  ConsultantIQ — 100 Prompt Stress Test")
    print(f"  Naive: {len(NAIVE_PROMPTS)} | Graph: {len(GRAPH_PROMPTS)} | Hybrid: {len(HYBRID_PROMPTS)}")
    print(f"  Total: {len(ALL_TESTS)}")
    print(f"{'='*60}\n")

    # Load retrievers
    print("Loading Naive RAG...")
    from naive_rag.retriever import RAGRetriever
    naive = RAGRetriever()

    print("Loading Graph RAG...")
    from graph_rag.retriever_graph import GraphRetriever
    graph = GraphRetriever()

    print("Loading Hybrid RAG...")
    from hybrid_rag.query_hybrid import HybridRetriever
    hybrid = HybridRetriever()

    log = _load_log()
    success, errors = 0, 0

    for i, (question, mode) in enumerate(ALL_TESTS, 1):
        print(f"[{i:3d}/{len(ALL_TESTS)}] ({mode:10s}) {question[:55]}...", end=" ", flush=True)

        t0 = time.time()
        try:
            context_text = ""

            if mode == "Naive RAG":
                result = naive.ask(question, top_k=5, verbose=False)
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
                num_chunks = len(chunks)
                context_text = "\n".join((c.get("cleaned_text") or c.get("chunk_text") or "") for c in chunks[:5])

            elif mode == "Graph RAG":
                import io, contextlib
                subgraph = graph.retrieve(question, top_k=5)
                nodes = subgraph.get("nodes", [])
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    answer = graph.ask(question, top_k=5)
                sources_list = list({n.get("source", "") for n in nodes if n.get("source")})
                match_scores = [n.get("_match_score", 0) for n in nodes if n.get("_match_score", 0) > 0]
                avg_score = sum(match_scores) / len(match_scores) if match_scores else (
                    min(len(nodes) / 5, 1.0) if nodes else 0
                )
                num_chunks = len(nodes)
                context_text = "\n".join(f"{n.get('name','')}: {n.get('description','')}" for n in nodes)

            elif mode == "Hybrid RAG":
                import io, contextlib
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    answer = hybrid.ask(question)
                # Clean terminal formatting
                clean_lines = []
                for ln in answer.split("\n"):
                    s = ln.strip()
                    if s.startswith("=") or s.startswith("──") or s.startswith("? "):
                        continue
                    clean_lines.append(ln)
                answer = "\n".join(clean_lines).strip()
                # Get context from both sources
                graph_nodes = []
                try:
                    sub = hybrid.graph.retrieve(question, top_k=5)
                    graph_nodes = sub.get("nodes", [])
                    g_ctx = "\n".join(f"{n.get('name','')}: {n.get('description','')}" for n in graph_nodes)
                except Exception:
                    g_ctx = ""
                naive_chunks_h = []
                try:
                    naive_chunks_h = hybrid.naive.retrieve(question, top_k=5) if hybrid.naive else []
                    if not isinstance(naive_chunks_h, list):
                        naive_chunks_h = []
                    n_ctx = "\n".join((c.get("cleaned_text") or c.get("chunk_text") or "") for c in naive_chunks_h[:5])
                except Exception:
                    n_ctx = ""
                context_text = g_ctx + "\n" + n_ctx

                # Sources from both graph nodes and naive chunks
                g_sources = {n.get("source", "") for n in graph_nodes if n.get("source")}
                n_sources = {c.get("source", "") for c in naive_chunks_h if c.get("source")}
                sources_list = list(g_sources | n_sources)

                # Score: blend graph match scores with naive retrieval scores
                g_match = [n.get("_match_score", 0) for n in graph_nodes if n.get("_match_score", 0) > 0]
                graph_score = sum(g_match) / len(g_match) if g_match else 0
                naive_scores_h = []
                for c in naive_chunks_h:
                    s = (c.get("@search.reranker_score") or c.get("_score_rrf")
                         or c.get("_score_vector") or c.get("_score_fulltext") or 0)
                    try:
                        v = float(s)
                        if v > 0:
                            naive_scores_h.append(v)
                    except (ValueError, TypeError):
                        pass
                naive_score = sum(naive_scores_h) / len(naive_scores_h) if naive_scores_h else 0
                if graph_score > 0 and naive_score > 0:
                    avg_score = (graph_score + naive_score) / 2
                else:
                    avg_score = graph_score or naive_score or 0
                num_chunks = len(graph_nodes) + len(naive_chunks_h)

            elapsed = time.time() - t0

            # Evaluate
            eval_scores = _evaluate_answer(question, context_text, answer)

            log.append({
                "question":      question,
                "effective_q":   question,
                "timestamp":     datetime.now().isoformat(timespec="seconds"),
                "mode":          mode,
                "response_time": round(elapsed, 2),
                "num_chunks":    num_chunks,
                "avg_score":     round(avg_score, 4),
                "answer_length": len(answer),
                "reformulated":  False,
                "used_memory":   False,
                "sources":       sources_list,
                "test_run":      True,
                "groundedness":  eval_scores["groundedness"],
                "relevancy":     eval_scores["relevancy"],
                "completeness":  eval_scores["completeness"],
                "hallucination": eval_scores["hallucination"],
            })

            success += 1
            g = eval_scores["groundedness"]
            r = eval_scores["relevancy"]
            c = eval_scores["completeness"]
            h = eval_scores["hallucination"]
            print(f"OK ({elapsed:.1f}s) G:{g} R:{r} C:{c} H:{h}")

        except Exception as e:
            elapsed = time.time() - t0
            errors += 1
            print(f"ERR ({elapsed:.1f}s) — {str(e)[:60]}")

            log.append({
                "question":      question,
                "effective_q":   question,
                "timestamp":     datetime.now().isoformat(timespec="seconds"),
                "mode":          mode,
                "response_time": round(elapsed, 2),
                "num_chunks":    0,
                "avg_score":     0,
                "answer_length": 0,
                "reformulated":  False,
                "used_memory":   False,
                "sources":       [],
                "test_run":      True,
                "error":         str(e)[:200],
                "groundedness":  0, "relevancy": 0, "completeness": 0, "hallucination": 0,
            })

    # Save all results at once
    print(f"\nSaving {len(log)} log entries...")
    _save_log(log)

    print(f"\n{'='*60}")
    print(f"  RESULTS")
    print(f"  Success: {success} | Errors: {errors} | Total: {len(ALL_TESTS)}")
    print(f"{'='*60}")

    # Per-mode summary
    test_entries = [e for e in log if e.get("test_run") and not e.get("error")]
    for mode in ["Naive RAG", "Graph RAG", "Hybrid RAG"]:
        me = [e for e in test_entries if e.get("mode") == mode]
        if me:
            avg_time = sum(e["response_time"] for e in me) / len(me)
            avg_g = sum(e.get("groundedness", 0) for e in me) / len(me)
            avg_r = sum(e.get("relevancy", 0) for e in me) / len(me)
            avg_c = sum(e.get("completeness", 0) for e in me) / len(me)
            avg_h = sum(e.get("hallucination", 0) for e in me) / len(me)
            print(f"\n  {mode} ({len(me)} queries):")
            print(f"    Avg Time:         {avg_time:.1f}s")
            print(f"    Groundedness:     {avg_g:.2f}")
            print(f"    Relevancy:        {avg_r:.2f}")
            print(f"    Completeness:     {avg_c:.2f}")
            print(f"    No Hallucination: {avg_h:.2f}")

    print(f"\nDone! Check Analytics in the Streamlit app.")


if __name__ == "__main__":
    run_tests()
