"""
analytics_rag.py
Reads evaluation/results/query_log.json and computes summary stats + charts
for the ConsultantIQ analytics dashboard.
"""

import json
import logging
from pathlib import Path
from collections import Counter

logger = logging.getLogger(__name__)

QUERY_LOG = Path(__file__).parent / "evaluation" / "results" / "query_log.json"


def _load_entries() -> list:
    try:
        if not QUERY_LOG.exists():
            return []
        with open(QUERY_LOG, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Failed to load query_log.json: {e}")
        return []


def compute_summary() -> dict:
    entries = _load_entries()
    total = len(entries)

    if total == 0:
        return {
            "total_queries": 0,
            "avg_response_time": 0.0,
            "avg_score": 0.0,
            "reformulation_rate": 0.0,
            "mode_distribution": {},
            "top_sources": [],
        }

    response_times = [e.get("response_time", 0) for e in entries if e.get("response_time")]
    scores = [e.get("avg_score", 0) for e in entries if e.get("avg_score")]
    reformulated = sum(1 for e in entries if e.get("reformulated"))

    mode_counter = Counter()
    for e in entries:
        mode = e.get("mode", "Unknown")
        # Normalize mode names
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

    top_sources = [
        {"source": src, "count": count}
        for src, count in source_counter.most_common(8)
    ]

    return {
        "total_queries": total,
        "avg_response_time": round(sum(response_times) / len(response_times), 2) if response_times else 0.0,
        "avg_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "reformulation_rate": round(reformulated / total * 100, 1),
        "mode_distribution": dict(mode_counter),
        "top_sources": top_sources,
    }


def compute_charts() -> dict:
    from chart_generator_rag import ChartGenerator
    entries = _load_entries()
    generator = ChartGenerator(entries)
    return generator.generate_all()


def get_analytics() -> dict:
    summary = compute_summary()
    charts = compute_charts()
    return {"summary": summary, "charts": charts}
