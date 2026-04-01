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
    "What is the threat of substitute products in Porter's model?",
    "How does supplier bargaining power influence an industry?",
    "What criteria distinguish a 'Cash Cow' from a 'Question Mark' in the BCG Matrix?",
    "What are the limitations of Porter's Five Forces?",
    "How should a company transition a Question Mark into a Star?",
    "What is the purpose of the value chain in competitive analysis?",
    "How does firm infrastructure support the value chain?",
    "What is the role of procurement in Porter's Value Chain?",
    "How does technology development contribute to competitive advantage?",
    "What are the steps to construct a MECE issue tree?",
    "How do economies of scale act as a barrier to entry?",
    "What is the difference between horizontal and vertical integration in strategy?",
    # Digital Transformation (digital_transformation_playbook.pdf)
    "What is a digital maturity assessment?",
    "How should organizations measure digital transformation ROI?",
    "What are common resistance factors during digital adoption?",
    "How does cloud migration fit into a transformation roadmap?",
    "What KPIs should track digital transformation progress?",
    "What is the role of a transformation management office?",
    "How should legacy systems be addressed during digital transformation?",
    "What training approaches support digital upskilling?",
    # Financial Analysis (financial_analysis_toolkit.pdf)
    "What is enterprise value and how is it calculated?",
    "How do you calculate weighted average cost of capital?",
    "What are the key assumptions in a DCF model?",
    "How do you determine the terminal value of a business?",
    "What multiples are commonly used in comparable company analysis?",
    "How should a sensitivity analysis be structured in a financial model?",
    "What is the difference between levered and unlevered free cash flow?",
    "How do you normalize earnings for valuation purposes?",
    "What are common red flags in financial statement analysis?",
    # Client Engagement (client_engagement_best_practices.docx)
    "What is the structure of a hypothesis-driven engagement?",
    "How should consultants scope a new project?",
    "What are the phases of a typical consulting engagement?",
    "How do you build executive alignment early in a project?",
    "What techniques help manage difficult stakeholders?",
]

GRAPH_PROMPTS = [
    # Entity/relationship focused questions
    "How does threat of substitutes connect to buyer behavior?",
    "What is the relationship between supplier power and input costs?",
    "How do barriers to entry relate to industry profitability?",
    "What connects the value chain to competitive positioning?",
    "How does human resource management link to firm performance in the value chain?",
    "What is the relationship between cash cows and investment strategy?",
    "How does digital maturity relate to organizational readiness?",
    "What connects cloud infrastructure to operational efficiency?",
    "How does enterprise value relate to equity value?",
    "What is the link between WACC and discount rates in valuation?",
    "How do terminal value assumptions affect DCF outcomes?",
    "What connects revenue growth to market share in strategic analysis?",
    "How does hypothesis-driven consulting relate to the pyramid principle?",
    "What is the relationship between project scoping and deliverable quality?",
    "How do executive sponsors influence transformation governance?",
    "What connects sensitivity analysis to risk management?",
    "How does industry concentration relate to competitive rivalry?",
    "What links free cash flow to enterprise valuation?",
    "How does technology pillar connect to the other transformation pillars?",
    "What is the relationship between stakeholder mapping and engagement planning?",
    "How do economies of scale relate to cost leadership strategy?",
    "What connects issue trees to root cause analysis?",
    "How does the BCG Matrix relate to resource allocation decisions?",
    "What links digital KPIs to business outcome measurement?",
    "How does procurement strategy connect to supplier bargaining power?",
    "What is the relationship between legacy systems and transformation risk?",
    "How do trading comparables relate to market sentiment?",
    "What connects change resistance to talent management?",
    "How does firm infrastructure enable all value chain activities?",
    "What is the relationship between engagement phases and stakeholder communication?",
    "How do financial red flags connect to due diligence?",
    "What links MECE structuring to problem decomposition?",
    "How does market growth connect to the Question Mark quadrant?",
]

HYBRID_PROMPTS = [
    # Complex analytical questions needing both context types
    "How would you use both the value chain and financial analysis to assess a target company?",
    "Compare the role of governance in digital transformation versus financial modeling.",
    "What strategic frameworks and financial tools support a market entry decision?",
    "How should a consultant combine stakeholder management with the pyramid principle for C-suite presentations?",
    "Explain how sensitivity analysis in financial models complements strategic scenario planning.",
    "What is the end-to-end process for evaluating a business unit using BCG Matrix and DCF?",
    "How do digital transformation KPIs align with financial performance metrics?",
    "Compare the risk factors in digital transformation with financial modeling assumptions.",
    "How should value chain analysis and financial statement analysis be used together in due diligence?",
    "What frameworks help structure a consulting engagement focused on cost reduction?",
    "How can the MECE principle improve the structure of a financial model?",
    "Compare the approach to measuring ROI in digital transformation versus capital investments.",
    "What is the relationship between Porter's Five Forces and comparable company selection?",
    "How should a consultant present valuation findings using the pyramid principle?",
    "Explain how change management and stakeholder engagement work together during transformation.",
    "What combination of tools would you use to assess industry attractiveness and company valuation?",
    "How do quick wins in transformation relate to cash flow improvement?",
    "Compare the role of executive sponsorship in client engagements versus digital programs.",
    "How should a consultant integrate strategic analysis with financial due diligence?",
    "What are the common pitfalls across strategic planning, financial analysis, and digital transformation?",
    "How does the value chain framework inform digital investment priorities?",
    "Compare hypothesis-driven consulting with scenario-based financial modeling.",
    "What is the comprehensive approach to evaluating competitive threats using all available frameworks?",
    "How do consulting engagement best practices apply to a digital transformation program?",
    "Explain how EBITDA margins relate to competitive positioning within an industry.",
    "What frameworks help prioritize which business units to digitally transform first?",
    "How should a consultant assess whether to build, buy, or partner using strategic and financial analysis?",
    "Compare stakeholder management approaches for financial restructuring versus digital programs.",
    "What is the integrated approach to assessing a company before an acquisition?",
    "How can issue trees structure both a strategic assessment and a financial analysis workstream?",
    "What connects client engagement phases to the stages of a digital transformation roadmap?",
    "How do barriers to entry influence both strategic recommendations and valuation multiples?",
    "What best practices apply when presenting both strategic and financial findings to a board?",
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
    from collections import Counter as _Counter

    _stops = {"the","and","for","are","with","that","this","from","have","has",
              "been","was","were","will","can","which","their","they","also",
              "more","than","into","such","each","about","between","should",
              "these","other","not","but","its","all","any","our","your",
              "what","how","does","who","when","where","why","you","use",
              "would","could","may","might","must","shall","need","used"}

    def _tok(text):
        return [w for w in _re.findall(r'[a-z]{3,}', text.lower())]

    def _cos(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        na = _math.sqrt(sum(x * x for x in a))
        nb = _math.sqrt(sum(x * x for x in b))
        return dot / (na * nb) if na > 0 and nb > 0 else 0.0

    def _rescale(raw, floor=0.3, ceiling=0.9):
        return min(1.0, max(0.0, (raw - floor) / (ceiling - floor)))

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

    def _kw_recall(q, ctx, ans):
        aw = set(_tok(ans))
        if not aw:
            return 0.0
        # Question keyword coverage
        qw = set(_tok(q)) - _stops
        q_cov = len(qw & aw) / len(qw) if qw else 0.0
        # Context key-term coverage (top 20 frequent terms)
        ctx_filt = [w for w in _tok(ctx) if w not in _stops and len(w) > 3]
        if not ctx_filt:
            return q_cov
        key_terms = {w for w, _ in _Counter(ctx_filt).most_common(20)}
        ctx_cov = len(key_terms & aw) / len(key_terms) if key_terms else 0.0
        return 0.5 * q_cov + 0.5 * ctx_cov

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
        embed_ground = _rescale(_cos(va, vc))
        embed_relev = _rescale(_cos(va, vq))
    except Exception:
        embed_ground = 0.0
        embed_relev = 0.0

    rp, rr = _rouge_l(context, answer)
    kw = _kw_recall(question, context, answer)

    return {
        "groundedness":  round(embed_ground, 2),
        "relevancy":     round(embed_relev, 2),
        "completeness":  round(0.5 * kw + 0.5 * rr, 2),
        "hallucination": round(0.4 * rp + 0.6 * embed_ground, 2),
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
