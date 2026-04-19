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
from pathlib import Path
from collections import Counter

logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "evaluation" / "results"
QUERY_LOG   = RESULTS_DIR / "query_log.json"


# ── Loaders ──────────────────────────────────────────────────

def _load_query_log() -> list:
    try:
        if not QUERY_LOG.exists():
            return []
        with open(QUERY_LOG, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Failed to load query_log.json: {e}")
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
    if "Hybrid" in mode:
        return "Hybrid RAG"
    if "Graph" in mode or "graph" in mode:
        return "Graph RAG"
    if "Naive" in mode or "naive" in mode:
        return "Naive RAG"
    return "Unknown"


# ── Summary computation ───────────────────────────────────────

def compute_summary() -> dict:
    entries     = _load_query_log()
    comparisons = _load_comparison_files()

    total = len(entries)

    # ── Operational metrics from query_log ──────────────────
    response_times = [e["response_time"] for e in entries if e.get("response_time")]
    scores         = [e["avg_score"]      for e in entries if e.get("avg_score")]
    reformulated   = sum(1 for e in entries if e.get("reformulated"))

    mode_counter = Counter()
    for e in entries:
        mode = e.get("mode", "Unknown")
        if "Hybrid" in mode:
            mode_counter["Hybrid RAG"] += 1
        elif "Graph" in mode:
            mode_counter["Graph RAG"] += 1
        elif "Naive" in mode:
            mode_counter["Naive RAG"] += 1
        else:
            mode_counter[mode] += 1

    source_counter = Counter()
    for e in entries:
        for src in e.get("sources", []):
            source_counter[src] += 1

    # ── Generation quality from query_log (LLM-as-judge entries) ──
    def _avg_metric(field, subset=None):
        src = subset if subset is not None else entries
        vals = [e[field] for e in src if isinstance(e.get(field), (int, float))]
        return round(sum(vals) / len(vals), 4) if vals else None

    groundedness  = _avg_metric("groundedness")
    relevancy     = _avg_metric("relevancy")
    completeness  = _avg_metric("completeness")
    hallucination = _avg_metric("hallucination")

    # ── Per-mode quality breakdown ────────────────────────────
    def _mode_entries(mode_key):
        return [e for e in entries if _normalize_mode_str(e.get("mode", "")) == mode_key]

    per_mode_quality = {}
    for mode_label in ("Naive RAG", "Graph RAG"):
        subset = _mode_entries(mode_label)
        if subset:
            per_mode_quality[mode_label] = {
                "groundedness":  _avg_metric("groundedness",  subset),
                "relevancy":     _avg_metric("relevancy",     subset),
                "completeness":  _avg_metric("completeness",  subset),
                "hallucination": _avg_metric("hallucination", subset),
                "count":         len(subset),
            }

    # ── Retrieval metrics from comparison files ───────────────
    retrieval_summary = _aggregate_retrieval(comparisons)

    def _avg(lst):
        return round(sum(lst) / len(lst), 4) if lst else 0.0

    return {
        "total_queries":       total,
        "avg_response_time":   round(_avg(response_times), 2),
        "avg_score":           round(_avg(scores), 4),
        "reformulation_rate":  round(reformulated / total * 100, 1) if total else 0.0,
        "mode_distribution":   dict(mode_counter),
        "top_sources":         [{"source": s, "count": c} for s, c in source_counter.most_common(8)],
        # Generation quality
        "groundedness":        groundedness,
        "relevancy":           relevancy,
        "completeness":        completeness,
        "hallucination":       hallucination,
        # Retrieval quality (from comparison evals)
        "retrieval":           retrieval_summary,
        # Per-mode generation quality
        "per_mode_quality":    per_mode_quality,
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
