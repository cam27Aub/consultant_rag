"""
chart_generator_rag.py
Server-side chart generation using matplotlib.
Generates base64-encoded PNG images for the ConsultantIQ analytics dashboard.
"""

import io
import base64
import logging
from collections import Counter, defaultdict
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)

# ── Brand Colors ──────────────────────────────────────────────
NAVY       = "#1F3564"
NAVY_LIGHT = "#2E74B5"
GOLD       = "#C8A951"
GREEN      = "#059669"
RED        = "#DC2626"
ORANGE     = "#D97706"
LIGHT_BG   = "#F8F9FA"
BORDER     = "#E5E7EB"
TEXT       = "#374151"
MUTED      = "#9CA3AF"

MODE_COLORS = {
    "Naive RAG":  NAVY,
    "Graph RAG":  NAVY_LIGHT,
    "Hybrid RAG": GOLD,
    "Unknown":    MUTED,
}

QUALITY_COLORS = {
    "Groundedness":  GREEN,
    "Relevancy":     NAVY_LIGHT,
    "Completeness":  GOLD,
    "Hallucination": RED,
}

SYSTEM_COLORS = {
    "naive":  NAVY,
    "graph":  NAVY_LIGHT,
    "hybrid": GOLD,
    "overall": MUTED,
}


# ── Helpers ───────────────────────────────────────────────────

def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=LIGHT_BG, edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def _style_ax(ax, title="", xlabel="", ylabel=""):
    ax.set_facecolor(LIGHT_BG)
    if title:
        ax.set_title(title, fontsize=12, fontweight="bold", color=TEXT, pad=10)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=9, color=MUTED)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9, color=MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(BORDER)
    ax.spines["bottom"].set_color(BORDER)
    ax.grid(axis="y", color=BORDER, linewidth=0.6, linestyle="--", alpha=0.8)


def _normalize_mode(mode: str) -> str:
    if "Hybrid" in mode:
        return "Hybrid RAG"
    if "Graph" in mode:
        return "Graph RAG"
    if "Naive" in mode:
        return "Naive RAG"
    return "Unknown"


class ChartGenerator:

    def __init__(self, entries: list, comparisons: list, summary: dict):
        self.entries     = entries
        self.comparisons = comparisons
        self.summary     = summary
        self._now        = datetime.utcnow()

    # ── 1. Mode Distribution Donut ────────────────────────────

    def chart_mode_distribution(self) -> str:
        mode_counter = Counter(_normalize_mode(e.get("mode", "Unknown")) for e in self.entries)
        if not mode_counter:
            return self._empty_chart("No query data yet")

        labels = list(mode_counter.keys())
        sizes  = list(mode_counter.values())
        colors = [MODE_COLORS.get(l, MUTED) for l in labels]

        fig, ax = plt.subplots(figsize=(6, 5), facecolor=LIGHT_BG)
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, colors=colors,
            autopct="%1.1f%%", startangle=90,
            wedgeprops=dict(width=0.45, edgecolor="white", linewidth=2),
            textprops={"fontsize": 10, "color": TEXT},
        )
        for t in autotexts:
            t.set_fontsize(9)
            t.set_fontweight("bold")
            t.set_color("white")
        ax.set_title("Query Mode Distribution", fontsize=12, fontweight="bold", color=TEXT, pad=12)
        ax.set_ylabel("")
        return _fig_to_base64(fig)

    # ── 2. Response Time Trend ────────────────────────────────

    def chart_response_time_trend(self) -> str:
        valid = sorted(
            [e for e in self.entries if e.get("timestamp") and e.get("response_time")],
            key=lambda x: x["timestamp"]
        )[-50:]

        if not valid:
            return self._empty_chart("No response time data yet")

        labels = list(range(1, len(valid) + 1))
        times  = [e["response_time"] for e in valid]
        colors = [MODE_COLORS.get(_normalize_mode(e.get("mode", "")), MUTED) for e in valid]

        fig, ax = plt.subplots(figsize=(10, 4), facecolor=LIGHT_BG)
        ax.fill_between(labels, times, alpha=0.08, color=NAVY)
        ax.plot(labels, times, color=NAVY, linewidth=1.5, zorder=2)
        ax.scatter(labels, times, c=colors, s=30, zorder=3, edgecolors="white", linewidths=0.5)

        avg = sum(times) / len(times)
        ax.axhline(avg, color=GOLD, linewidth=1.2, linestyle="--", alpha=0.9,
                   label=f"Avg: {avg:.1f}s")
        ax.legend(fontsize=8, frameon=False)
        _style_ax(ax, "Response Time — Last 50 Queries", xlabel="Query #", ylabel="Seconds")
        ax.set_xlim(1, len(labels))
        ax.set_ylim(bottom=0)
        return _fig_to_base64(fig)

    # ── 3. Generation Quality Metrics ────────────────────────

    def chart_quality_metrics(self) -> str:
        s = self.summary
        metrics = {
            "Groundedness":  s.get("groundedness"),
            "Relevancy":     s.get("relevancy"),
            "Completeness":  s.get("completeness"),
            "Hallucination": s.get("hallucination"),
        }
        available = {k: v for k, v in metrics.items() if v is not None}

        if not available:
            return self._empty_chart("Run evaluation to see quality metrics\n(python evaluation/evaluate.py)")

        labels = list(available.keys())
        values = list(available.values())
        colors = [QUALITY_COLORS.get(l, NAVY) for l in labels]

        fig, ax = plt.subplots(figsize=(8, 5), facecolor=LIGHT_BG)
        bars = ax.bar(labels, values, color=colors, edgecolor="white",
                      linewidth=0.8, width=0.5)

        for bar, v in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.015,
                    f"{v:.3f}",
                    ha="center", fontsize=10, color=TEXT, fontweight="bold")

        ax.set_ylim(0, 1.15)
        ax.axhline(1.0, color=BORDER, linewidth=0.8, linestyle="--")
        _style_ax(ax, "Generation Quality Metrics (avg across all queries)", ylabel="Score (0 – 1)")

        # Note for hallucination (lower = better)
        if "Hallucination" in available:
            ax.text(labels.index("Hallucination"), available["Hallucination"] + 0.05,
                    "lower↑better", ha="center", fontsize=7, color=RED, style="italic")

        return _fig_to_base64(fig)

    # ── 4. Retrieval Metrics (Recall / Precision / MRR) ──────

    def chart_retrieval_metrics(self) -> str:
        retrieval = self.summary.get("retrieval", {})
        systems   = [s for s in retrieval if s != "overall"]

        if not systems:
            return self._empty_chart("Run evaluation to see retrieval metrics\n(python evaluation/evaluate.py --compare-modes)")

        KEYS = ["Recall@1", "Recall@3", "Recall@5", "Precision@1", "Precision@3", "Precision@5", "MRR"]
        x     = np.arange(len(KEYS))
        width = 0.25 / max(len(systems), 1)

        fig, ax = plt.subplots(figsize=(12, 5), facecolor=LIGHT_BG)

        for i, sys_name in enumerate(sorted(systems)):
            data   = retrieval[sys_name]
            values = [data.get(k) if data.get(k) is not None else 0.0 for k in KEYS]
            color  = SYSTEM_COLORS.get(sys_name, PALETTE[i % len(PALETTE)])
            offset = (i - len(systems) / 2 + 0.5) * (width + 0.02)
            bars   = ax.bar(x + offset, values, width + 0.02, label=sys_name.title(),
                            color=color, edgecolor="white", linewidth=0.6, alpha=0.9)
            for bar, v in zip(bars, values):
                if v > 0:
                    ax.text(bar.get_x() + bar.get_width() / 2,
                            bar.get_height() + 0.01,
                            f"{v:.2f}",
                            ha="center", fontsize=6, color=TEXT)

        ax.set_xticks(x)
        ax.set_xticklabels(KEYS, fontsize=8, color=TEXT)
        ax.set_ylim(0, 1.2)
        ax.legend(fontsize=9, frameon=False)
        _style_ax(ax, "Retrieval Metrics by System (Recall / Precision / MRR)", ylabel="Score (0 – 1)")
        return _fig_to_base64(fig)

    # ── 5. Top Source Documents ───────────────────────────────

    def chart_top_sources(self) -> str:
        source_counter: Counter = Counter()
        for e in self.entries:
            for src in e.get("sources", []):
                name = src if len(src) <= 35 else src[:32] + "..."
                source_counter[name] += 1

        top = source_counter.most_common(8)
        if not top:
            return self._empty_chart("No source data yet")

        labels = [t[0] for t in reversed(top)]
        counts = [t[1] for t in reversed(top)]
        bar_colors = [NAVY if i % 2 == 0 else NAVY_LIGHT for i in range(len(labels))]

        fig, ax = plt.subplots(figsize=(9, max(4, len(labels) * 0.65)), facecolor=LIGHT_BG)
        bars = ax.barh(labels, counts, color=bar_colors, edgecolor="white",
                       linewidth=0.8, height=0.55)
        for bar, v in zip(bars, counts):
            ax.text(bar.get_width() + 0.1,
                    bar.get_y() + bar.get_height() / 2,
                    str(v), va="center", fontsize=9, color=TEXT, fontweight="bold")

        ax.set_facecolor(LIGHT_BG)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(BORDER)
        ax.spines["bottom"].set_color(BORDER)
        ax.tick_params(colors=TEXT, labelsize=8)
        ax.set_title("Most Queried Source Documents", fontsize=12, fontweight="bold", color=TEXT, pad=10)
        ax.set_xlabel("Times retrieved", fontsize=9, color=MUTED)
        ax.grid(axis="x", color=BORDER, linewidth=0.6, linestyle="--", alpha=0.8)
        ax.set_xlim(right=max(counts) * 1.15)
        return _fig_to_base64(fig)

    # ── 6. Score by Mode ──────────────────────────────────────

    def chart_score_by_mode(self) -> str:
        mode_scores: dict = defaultdict(list)
        mode_times:  dict = defaultdict(list)

        for e in self.entries:
            m = _normalize_mode(e.get("mode", "Unknown"))
            if e.get("avg_score"):
                mode_scores[m].append(e["avg_score"])
            if e.get("response_time"):
                mode_times[m].append(e["response_time"])

        modes = sorted(mode_scores.keys())
        if not modes:
            return self._empty_chart("No mode performance data yet")

        avg_scores = [sum(mode_scores[m]) / len(mode_scores[m]) for m in modes]
        avg_times  = [sum(mode_times[m])  / len(mode_times[m]) if mode_times[m] else 0 for m in modes]
        bar_colors = [MODE_COLORS.get(m, MUTED) for m in modes]

        x     = np.arange(len(modes))
        width = 0.35

        fig, ax1 = plt.subplots(figsize=(8, 5), facecolor=LIGHT_BG)
        ax2 = ax1.twinx()

        bars1 = ax1.bar(x - width / 2, avg_scores, width, color=bar_colors,
                        alpha=0.9, edgecolor="white", linewidth=0.8, label="Avg Score")
        bars2 = ax2.bar(x + width / 2, avg_times,  width, color=bar_colors,
                        alpha=0.4, edgecolor="white", linewidth=0.8, label="Avg Response Time (s)")

        for bar, v in zip(bars1, avg_scores):
            ax1.text(bar.get_x() + bar.get_width() / 2,
                     bar.get_height() + 0.02,
                     f"{v:.2f}", ha="center", fontsize=8, color=TEXT, fontweight="bold")
        for bar, v in zip(bars2, avg_times):
            ax2.text(bar.get_x() + bar.get_width() / 2,
                     bar.get_height() + 0.3,
                     f"{v:.1f}s", ha="center", fontsize=8, color=TEXT)

        ax1.set_xticks(x)
        ax1.set_xticklabels(modes, fontsize=9, color=TEXT)
        ax1.set_ylabel("Avg Similarity Score", fontsize=9, color=MUTED)
        ax2.set_ylabel("Avg Response Time (s)", fontsize=9, color=MUTED)
        _style_ax(ax1, "Performance by RAG Mode")
        ax1.set_facecolor(LIGHT_BG)
        fig.patch.set_facecolor(LIGHT_BG)

        lines1, l1 = ax1.get_legend_handles_labels()
        lines2, l2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, l1 + l2, fontsize=8, frameon=False)
        return _fig_to_base64(fig)

    # ── Empty placeholder ─────────────────────────────────────

    def _empty_chart(self, message: str) -> str:
        fig, ax = plt.subplots(figsize=(8, 4), facecolor=LIGHT_BG)
        ax.set_facecolor(LIGHT_BG)
        for spine in ax.spines.values():
            spine.set_color(BORDER)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.text(0.5, 0.5, message, ha="center", va="center",
                color=MUTED, fontsize=10, style="italic",
                transform=ax.transAxes)
        return _fig_to_base64(fig)

    # ── Generate All ──────────────────────────────────────────

    def generate_all(self) -> dict:
        charts = {
            "mode_distribution":   ("Query Mode Distribution",              self.chart_mode_distribution),
            "response_time_trend": ("Response Time Trend",                  self.chart_response_time_trend),
            "quality_metrics":     ("Generation Quality Metrics",           self.chart_quality_metrics),
            "retrieval_metrics":   ("Retrieval Metrics by System",          self.chart_retrieval_metrics),
            "score_by_mode":       ("Performance by RAG Mode",              self.chart_score_by_mode),
            "top_sources":         ("Most Queried Source Documents",        self.chart_top_sources),
        }

        result = {}
        for key, (title, fn) in charts.items():
            try:
                result[key] = {"title": title, "image": fn()}
            except Exception as e:
                logger.error(f"Chart '{key}' failed: {e}")
                result[key] = {"title": title, "image": None}
        return result


PALETTE = [NAVY, NAVY_LIGHT, GOLD, GREEN, ORANGE, MUTED]
