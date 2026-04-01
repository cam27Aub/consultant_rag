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


def run_tests():
    import asyncio
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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

    retrievers = {
        "Naive RAG": naive,
        "Graph RAG": graph,
        "Hybrid RAG": hybrid,
    }

    log = _load_log()
    success, errors = 0, 0

    for i, (question, mode) in enumerate(ALL_TESTS, 1):
        print(f"[{i:3d}/{len(ALL_TESTS)}] ({mode:10s}) {question[:60]}...", end=" ", flush=True)

        t0 = time.time()
        try:
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

            elif mode == "Graph RAG":
                import io, contextlib
                subgraph = graph.retrieve(question, top_k=5)
                nodes = subgraph.get("nodes", [])
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    answer = graph.ask(question, top_k=5)
                sources_list = list({n.get("source", "") for n in nodes if n.get("source")})
                avg_score = min(len(nodes) / 5, 1.0) if nodes else 0
                num_chunks = len(nodes)

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
                sources_list = []
                avg_score = 0.5  # default for hybrid
                num_chunks = 5

            elapsed = time.time() - t0

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
            })

            success += 1
            print(f"OK ({elapsed:.1f}s, {len(answer)} chars)")

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
            })

    # Save all results at once
    print(f"\nSaving {len(log)} log entries...")
    _save_log(log)

    print(f"\n{'='*60}")
    print(f"  RESULTS")
    print(f"  Success: {success} | Errors: {errors} | Total: {len(ALL_TESTS)}")
    print(f"{'='*60}")

    # Per-mode summary
    test_entries = [e for e in log if e.get("test_run")]
    for mode in ["Naive RAG", "Graph RAG", "Hybrid RAG"]:
        mode_entries = [e for e in test_entries if e.get("mode") == mode and not e.get("error")]
        if mode_entries:
            avg_time = sum(e["response_time"] for e in mode_entries) / len(mode_entries)
            avg_sc = sum(e["avg_score"] for e in mode_entries) / len(mode_entries)
            avg_len = sum(e["answer_length"] for e in mode_entries) / len(mode_entries)
            print(f"\n  {mode}:")
            print(f"    Queries:        {len(mode_entries)}")
            print(f"    Avg Time:       {avg_time:.1f}s")
            print(f"    Avg Score:      {avg_sc:.4f}")
            print(f"    Avg Answer Len: {avg_len:.0f} chars")

    print(f"\nDone! Check Analytics in the Streamlit app.")


if __name__ == "__main__":
    run_tests()
