"""
analytics_rag.py
Reads evaluation/results/query_log.json + comparison_*.json
and computes full analytics for the ConsultantIQ dashboard.

Metrics covered:
  Generation : groundedness, relevancy, completeness, hallucination
  Retrieval  : Recall@1/3/5, Precision@1/3/5, MRR
  Operational: response_time, avg_score, reformulation_rate, mode distribution
"""

import json
import glob
import logging
import base64
import os
import requests as _requests
from pathlib import Path
from collections import Counter

logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "evaluation" / "results"
QUERY_LOG   = RESULTS_DIR / "query_log.json"

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


# ── Loaders ──────────────────────────────────────────────────

def _load_query_log() -> list:
    """
    Load query log. Strategy:
    - If GITHUB_TOKEN + GITHUB_REPO are set: always fetch from GitHub (live data,
      no local caching so Render always gets fresh data after the 5-min analytics cache expires).
    - Otherwise: read from local file (dev fallback).
    """
    token, repo = _gh_token(), _gh_repo()
    if token and repo:
        try:
            url = f"{_GITHUB_API}/repos/{repo}/contents/evaluation/results/query_log.json"
            r = _requests.get(
                url,
                headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"},
                timeout=20,
            )
            if r.status_code == 200:
                content = base64.b64decode(r.json()["content"]).decode("utf-8")
                data = json.loads(content)
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"GitHub query_log fetch failed: {e}")

    # Local fallback (dev without GitHub creds, or GitHub fetch failed)
    try:
        if QUERY_LOG.exists():
            with open(QUERY_LOG, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return data
    except Exception as e:
        logger.warning(f"Local query_log read failed: {e}")

    return []


def _load_comparison_files() -> list:
    """Load all comparison_*.json files, return list of system-level result dicts."""
    results = []
    pattern = str(RESULTS_DIR / "comparison_*.json")
    for path in sorted(glob.glob(pattern)):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                results.extend(data)
            elif isinstance(data, dict):
                results.append(data)
        except Exception as e:
            logger.error(f"Failed to load {path}: {e}")
    return results


def _normalize_mode_str(mode: str) -> str:
    m = mode.lower()
    if "hybrid" in m:
        return "Hybrid RAG"
    if "graph" in m:
        return "Graph RAG"
    if "naive" in m:
        return "Naive RAG"
    return "Unknown"


# ── Summary computation ───────────────────────────────────────

def compute_summary() -> dict:
    entries     = _load_query_log()
    comparisons = _load_comparison_files()

    # Separate live (real UI) queries from synthetic test_run entries
    live_entries = [e for e in entries if not e.get("test_run")]
    total        = len(live_entries)

    # ── Operational metrics — live queries only ───────────────
    response_times = [e["response_time"] for e in live_entries if e.get("response_time")]

    mode_counter = Counter()
    for e in live_entries:
        mode_counter[_normalize_mode_str(e.get("mode", "Unknown"))] += 1

    source_counter = Counter()
    for e in live_entries:
        for src in e.get("sources", []):
            source_counter[src] += 1

    # ── RAGAS metrics from query_log (LLM-as-judge entries) ──
    def _avg_metric(field, subset=None):
        src = subset if subset is not None else entries
        vals = [e[field] for e in src if isinstance(e.get(field), (int, float))]
        return round(sum(vals) / len(vals), 4) if vals else None

    faithfulness      = _avg_metric("faithfulness")
    answer_relevancy  = _avg_metric("answer_relevancy")
    context_precision = _avg_metric("context_precision")

    # ── Per-mode quality breakdown ────────────────────────────
    def _mode_entries(mode_key):
        return [e for e in entries if _normalize_mode_str(e.get("mode", "")) == mode_key]

    per_mode_quality = {}
    for mode_label in ("Naive RAG", "Graph RAG"):
        subset = _mode_entries(mode_label)
        if subset:
            per_mode_quality[mode_label] = {
                "faithfulness":      _avg_metric("faithfulness",      subset),
                "answer_relevancy":  _avg_metric("answer_relevancy",  subset),
                "context_precision": _avg_metric("context_precision", subset),
                "count":             len(subset),
            }

    # ── Retrieval metrics from comparison files ───────────────
    retrieval_summary = _aggregate_retrieval(comparisons)

    def _avg(lst):
        return round(sum(lst) / len(lst), 4) if lst else 0.0

    # ── Recent queries (last 15, newest first) ────────────────
    recent_qs = sorted(
        [e for e in entries if e.get("question") and not e.get("error")],
        key=lambda x: x.get("timestamp", ""),
        reverse=True,
    )[:15]
    recent_queries = [
        {
            "question":         e["question"][:120],
            "mode":             e.get("mode", "Unknown"),
            "timestamp":        e.get("timestamp", ""),
            "response_time":    e.get("response_time"),
            "faithfulness":     e.get("faithfulness"),
            "answer_relevancy": e.get("answer_relevancy"),
        }
        for e in recent_qs
    ]

    return {
        "total_queries":       total,
        "avg_response_time":   round(_avg(response_times), 2),
        "mode_distribution":   dict(mode_counter),
        "top_sources":         [{"source": s, "count": c} for s, c in source_counter.most_common(8)],
        # RAGAS metrics (global averages)
        "faithfulness":        faithfulness,
        "answer_relevancy":    answer_relevancy,
        "context_precision":   context_precision,
        # Per-mode RAGAS breakdown
        "per_mode_quality":    per_mode_quality,
        # Recent query feed
        "recent_queries":      recent_queries,
    }


def _aggregate_retrieval(comparisons: list) -> dict:
    """
    Average retrieval metrics across all comparison runs, grouped by system.
    Returns: {
      "naive":  {"Recall@1": ..., "Precision@1": ..., ..., "MRR": ...},
      "graph":  {...},
      "hybrid": {...},
      "overall": {...}  ← average across all systems
    }
    """
    METRICS = ["Recall@1", "Precision@1", "Recall@3", "Precision@3",
               "Recall@5", "Precision@5", "MRR"]

    buckets: dict[str, dict[str, list]] = {}

    for comp in comparisons:
        system = comp.get("system", "unknown").lower()
        retrieval = comp.get("retrieval", {})
        summary   = retrieval.get("summary", {})

        if system not in buckets:
            buckets[system] = {m: [] for m in METRICS}

        for m in METRICS:
            if isinstance(summary.get(m), (int, float)):
                buckets[system][m].append(summary[m])

    result = {}
    all_vals: dict[str, list] = {m: [] for m in METRICS}

    for system, data in buckets.items():
        result[system] = {}
        for m in METRICS:
            avg = round(sum(data[m]) / len(data[m]), 4) if data[m] else None
            result[system][m] = avg
            if avg is not None:
                all_vals[m].append(avg)

    # Overall average
    result["overall"] = {
        m: round(sum(all_vals[m]) / len(all_vals[m]), 4) if all_vals[m] else None
        for m in METRICS
    }

    return result


# ── Charts ────────────────────────────────────────────────────

def compute_charts(summary: dict) -> dict:
    from chart_generator_rag import ChartGenerator
    entries     = _load_query_log()
    comparisons = _load_comparison_files()
    generator   = ChartGenerator(entries, comparisons, summary)
    return generator.generate_all()


# ── Entry point ───────────────────────────────────────────────

_cache: dict = {"data": None, "ts": 0.0}
_CACHE_TTL   = 300  # 5 minutes — chart generation is expensive


def get_analytics(bust_cache: bool = False) -> dict:
    import time
    now = time.time()
    if not bust_cache and _cache["data"] and (now - _cache["ts"]) < _CACHE_TTL:
        return _cache["data"]
    summary = compute_summary()
    charts  = compute_charts(summary)
    result  = {"summary": summary, "charts": charts}
    _cache["data"] = result
    _cache["ts"]   = now
    return result
