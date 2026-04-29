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
    "Faithfulness":      GREEN,
    "Answer Relevancy":  NAVY_LIGHT,
    "Context Precision": GOLD,
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
    m = mode.lower()
    if "hybrid" in m:
        return "Hybrid RAG"
    if "graph" in m:
        return "Graph RAG"
    if "naive" in m:
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
        mode_counter = Counter(_normalize_mode(e.get("mode", "Unknown")) for e in self.entries if not e.get("test_run"))
        if not mode_counter:
            return self._empty_chart("No query data yet")

        labels = list(mode_counter.keys())
        sizes  = list(mode_counter.values())
        colors = [MODE_COLORS.get(l, MUTED) for l in labels]
        total  = sum(sizes)

        fig, ax = plt.subplots(figsize=(6, 5), facecolor=LIGHT_BG)
        wedges, _ = ax.pie(
            sizes, colors=colors, startangle=90,
            wedgeprops=dict(width=0.45, edgecolor="white", linewidth=2),
        )
        # Put percentage + count inside wedges manually to avoid matplotlib alignment bugs
        for wedge, label, size in zip(wedges, labels, sizes):
            angle = (wedge.theta1 + wedge.theta2) / 2
            import math
            r = 0.72
            x = r * math.cos(math.radians(angle))
            y = r * math.sin(math.radians(angle))
            pct = size / total * 100
            ax.text(x, y, f"{pct:.1f}%", ha="center", va="center",
                    fontsize=10, fontweight="bold", color="white")

        ax.legend(wedges, labels, loc="lower center", ncol=len(labels),
                  fontsize=9, frameon=False,
                  bbox_to_anchor=(0.5, -0.05))
        ax.set_title("Query Mode Distribution", fontsize=12, fontweight="bold", color=TEXT, pad=12)
        ax.set_ylabel("")
        return _fig_to_base64(fig)

    # ── 2. Response Time Trend ────────────────────────────────

    def chart_response_time_trend(self) -> str:
        all_valid = sorted(
            [e for e in self.entries
             if e.get("timestamp") and e.get("response_time") and not e.get("test_run")],
            key=lambda x: x["timestamp"]
        )

        if not all_valid:
            return self._empty_chart("No response time data yet")

        # Build per-mode sequences independently (each starts at query 1)
        def _mode_seq(mode_label):
            entries = [e for e in all_valid
                       if _normalize_mode(e.get("mode", "")) == mode_label][-50:]
            return [(i + 1, e["response_time"]) for i, e in enumerate(entries)]

        naive_pts = _mode_seq("Naive RAG")
        graph_pts = _mode_seq("Graph RAG")
        other_pts = [(i + 1, e["response_time"]) for i, e in enumerate(
            [e for e in all_valid
             if _normalize_mode(e.get("mode", "")) not in ("Naive RAG", "Graph RAG")][-50:]
        )]

        fig, ax = plt.subplots(figsize=(10, 4), facecolor=LIGHT_BG)

        for pts, color, label in [
            (naive_pts, NAVY,       "Naive RAG"),
            (graph_pts, NAVY_LIGHT, "Graph RAG"),
            (other_pts, GOLD,       "Other"),
        ]:
            if not pts:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            mode_avg = sum(ys) / len(ys)
            ax.plot(xs, ys, color=color, linewidth=1.5, label=f"{label} (avg {mode_avg:.1f}s)", zorder=2)
            ax.scatter(xs, ys, color=color, s=30, zorder=3,
                       edgecolors="white", linewidths=0.5)

        ax.legend(fontsize=8, frameon=False)
        _style_ax(ax, "Response Time by Mode", xlabel="Query # (per mode)", ylabel="Seconds")
        ax.set_ylim(bottom=0)
        return _fig_to_base64(fig)

    # ── 3. Generation Quality Metrics ────────────────────────

    def chart_quality_metrics(self) -> str:
        per_mode = self.summary.get("per_mode_quality", {})
        METRIC_KEYS   = ["faithfulness", "answer_relevancy", "context_precision"]
        METRIC_LABELS = ["Faithfulness", "Answer Relevancy", "Context Precision"]

        # Fall back to global single bars if no per-mode data
        if not per_mode:
            s = self.summary
            vals = [s.get(k) for k in METRIC_KEYS]
            available = [(lbl, v) for lbl, v in zip(METRIC_LABELS, vals) if v is not None]
            if not available:
                return self._empty_chart("Run evaluation to see quality metrics\n(python evaluation/test_100.py)")
            labels = [a[0] for a in available]
            values = [a[1] for a in available]
            colors = [QUALITY_COLORS.get(l, NAVY) for l in labels]
            fig, ax = plt.subplots(figsize=(8, 5), facecolor=LIGHT_BG)
            bars = ax.bar(labels, values, color=colors, edgecolor="white", linewidth=0.8, width=0.5)
            for bar, v in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.015,
                        f"{v:.3f}", ha="center", fontsize=10, color=TEXT, fontweight="bold")
            ax.set_ylim(0, 1.15)
            ax.axhline(1.0, color=BORDER, linewidth=0.8, linestyle="--")
            _style_ax(ax, "RAGAS Quality Metrics (avg across all queries)", ylabel="Score (0 – 1)")
            return _fig_to_base64(fig)

        # Grouped bars: one group per metric, one bar per mode
        modes      = list(per_mode.keys())
        mode_colors = [NAVY, NAVY_LIGHT, GOLD]
        x      = np.arange(len(METRIC_KEYS))
        n      = len(modes)
        width  = 0.30
        offsets = np.linspace(-(n - 1) / 2, (n - 1) / 2, n) * (width + 0.04)

        fig, ax = plt.subplots(figsize=(9, 5), facecolor=LIGHT_BG)

        for i, (mode, color) in enumerate(zip(modes, mode_colors)):
            vals = [per_mode[mode].get(k) or 0.0 for k in METRIC_KEYS]
            bars = ax.bar(x + offsets[i], vals, width, label=mode,
                          color=color, edgecolor="white", linewidth=0.8, alpha=0.92)
            for bar, v in zip(bars, vals):
                if v > 0:
                    ax.text(bar.get_x() + bar.get_width() / 2,
                            bar.get_height() + 0.012,
                            f"{v:.3f}", ha="center", fontsize=8, color=TEXT, fontweight="bold")

        ax.set_xticks(x)
        ax.set_xticklabels(METRIC_LABELS, fontsize=9, color=TEXT)
        ax.set_ylim(0, 1.18)
        ax.axhline(1.0, color=BORDER, linewidth=0.8, linestyle="--")
        ax.legend(fontsize=9, frameon=False, loc="upper right")
        _style_ax(ax, "RAGAS Quality Metrics — Naive RAG vs Graph RAG", ylabel="Score (0 – 1)")

        return _fig_to_base64(fig)

    # ── 4. Top Source Documents ───────────────────────────────

    def chart_top_sources(self) -> str:
        source_counter: Counter = Counter()
        for e in self.entries:
            if e.get("test_run"):  # exclude benchmark test entries
                continue
            for src in e.get("sources", []):
                # Aggregate by document name only (strip " / Page N" suffix)
                doc_name = src.split(" / Page ")[0].split(" / Slide ")[0].strip()
                label = doc_name if len(doc_name) <= 35 else doc_name[:32] + "..."
                source_counter[label] += 1

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
            "quality_metrics":     ("RAGAS Quality Metrics",                self.chart_quality_metrics),
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
