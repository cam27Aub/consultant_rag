"""
chart_generator_rag.py
Server-side chart generation using matplotlib.
Generates base64-encoded PNG images for the ConsultantIQ analytics dashboard.
Brand colors: navy #1F3564
"""

import io
import base64
import logging
from datetime import datetime, timedelta
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

logger = logging.getLogger(__name__)

# ── Brand Colors ──────────────────────────────────────────────
NAVY       = "#1F3564"
NAVY_LIGHT = "#2E74B5"
NAVY_MID   = "#3A5F9E"
GOLD       = "#C8A951"
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

PALETTE = [NAVY, NAVY_LIGHT, GOLD, "#5B8DD9", "#A78BFA", MUTED]


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

    def __init__(self, entries: list):
        self.entries = entries
        self._now = datetime.utcnow()

    # ── 1. Mode Distribution Donut ────────────────────────────

    def chart_mode_distribution(self) -> str:
        mode_counter = Counter(_normalize_mode(e.get("mode", "Unknown")) for e in self.entries)
        labels = list(mode_counter.keys())
        sizes  = list(mode_counter.values())
        colors = [MODE_COLORS.get(l, MUTED) for l in labels]

        fig, ax = plt.subplots(figsize=(6, 5), facecolor=LIGHT_BG)
        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            colors=colors,
            autopct="%1.1f%%",
            startangle=90,
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
        # Last 50 queries with valid timestamps
        entries_sorted = sorted(
            [e for e in self.entries if e.get("timestamp") and e.get("response_time")],
            key=lambda x: x["timestamp"]
        )[-50:]

        if not entries_sorted:
            fig, ax = plt.subplots(figsize=(10, 4), facecolor=LIGHT_BG)
            ax.text(0.5, 0.5, "No data", ha="center", va="center", color=MUTED)
            return _fig_to_base64(fig)

        labels = list(range(1, len(entries_sorted) + 1))
        times  = [e["response_time"] for e in entries_sorted]
        modes  = [_normalize_mode(e.get("mode", "Unknown")) for e in entries_sorted]
        colors = [MODE_COLORS.get(m, MUTED) for m in modes]

        fig, ax = plt.subplots(figsize=(10, 4), facecolor=LIGHT_BG)
        ax.fill_between(labels, times, alpha=0.08, color=NAVY)
        ax.plot(labels, times, color=NAVY, linewidth=1.5, zorder=2)
        ax.scatter(labels, times, c=colors, s=30, zorder=3, edgecolors="white", linewidths=0.5)

        # Avg line
        avg = sum(times) / len(times)
        ax.axhline(avg, color=GOLD, linewidth=1.2, linestyle="--", alpha=0.8, label=f"Avg: {avg:.1f}s")
        ax.legend(fontsize=8, frameon=False)

        _style_ax(ax, "Response Time — Last 50 Queries", xlabel="Query #", ylabel="Seconds")
        ax.set_xlim(1, len(labels))
        ax.set_ylim(bottom=0)
        return _fig_to_base64(fig)

    # ── 3. Avg Score by Mode ──────────────────────────────────

    def chart_score_by_mode(self) -> str:
        mode_scores: dict[str, list] = defaultdict(list)
        mode_times:  dict[str, list] = defaultdict(list)

        for e in self.entries:
            m = _normalize_mode(e.get("mode", "Unknown"))
            if e.get("avg_score"):
                mode_scores[m].append(e["avg_score"])
            if e.get("response_time"):
                mode_times[m].append(e["response_time"])

        modes = sorted(mode_scores.keys())
        if not modes:
            fig, ax = plt.subplots(figsize=(8, 4), facecolor=LIGHT_BG)
            ax.text(0.5, 0.5, "No data", ha="center", va="center", color=MUTED)
            return _fig_to_base64(fig)

        avg_scores = [sum(mode_scores[m]) / len(mode_scores[m]) for m in modes]
        avg_times  = [sum(mode_times[m])  / len(mode_times[m])  if mode_times[m] else 0 for m in modes]
        bar_colors = [MODE_COLORS.get(m, MUTED) for m in modes]

        x     = np.arange(len(modes))
        width = 0.35

        fig, ax1 = plt.subplots(figsize=(8, 5), facecolor=LIGHT_BG)
        ax2 = ax1.twinx()

        bars1 = ax1.bar(x - width / 2, avg_scores, width, color=bar_colors, alpha=0.9,
                        edgecolor="white", linewidth=0.8, label="Avg Score")
        bars2 = ax2.bar(x + width / 2, avg_times,  width, color=bar_colors, alpha=0.4,
                        edgecolor="white", linewidth=0.8, label="Avg Response Time (s)")

        for bar, v in zip(bars1, avg_scores):
            ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                     f"{v:.2f}", ha="center", fontsize=8, color=TEXT, fontweight="bold")
        for bar, v in zip(bars2, avg_times):
            ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                     f"{v:.1f}s", ha="center", fontsize=8, color=TEXT)

        ax1.set_xticks(x)
        ax1.set_xticklabels(modes, fontsize=9, color=TEXT)
        ax1.set_ylabel("Avg Similarity Score", fontsize=9, color=MUTED)
        ax2.set_ylabel("Avg Response Time (s)", fontsize=9, color=MUTED)
        _style_ax(ax1, "Performance by RAG Mode")
        ax1.set_facecolor(LIGHT_BG)
        fig.patch.set_facecolor(LIGHT_BG)

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=8, frameon=False)

        return _fig_to_base64(fig)

    # ── 4. Top Source Documents ───────────────────────────────

    def chart_top_sources(self) -> str:
        source_counter: Counter = Counter()
        for e in self.entries:
            for src in e.get("sources", []):
                # Shorten long filenames
                name = src if len(src) <= 32 else src[:29] + "..."
                source_counter[name] += 1

        top = source_counter.most_common(8)
        if not top:
            fig, ax = plt.subplots(figsize=(9, 5), facecolor=LIGHT_BG)
            ax.text(0.5, 0.5, "No data", ha="center", va="center", color=MUTED)
            return _fig_to_base64(fig)

        labels = [t[0] for t in reversed(top)]
        counts = [t[1] for t in reversed(top)]
        bar_colors = [NAVY if i % 2 == 0 else NAVY_LIGHT for i in range(len(labels))]

        fig, ax = plt.subplots(figsize=(9, max(4, len(labels) * 0.6)), facecolor=LIGHT_BG)
        bars = ax.barh(labels, counts, color=bar_colors, edgecolor="white",
                       linewidth=0.8, height=0.55)
        for bar, v in zip(bars, counts):
            ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
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

    # ── Generate All ──────────────────────────────────────────

    def generate_all(self) -> dict:
        if not self.entries:
            return {}

        charts = {
            "mode_distribution":    ("Query Mode Distribution",          self.chart_mode_distribution),
            "response_time_trend":  ("Response Time Trend",              self.chart_response_time_trend),
            "score_by_mode":        ("Performance by RAG Mode",          self.chart_score_by_mode),
            "top_sources":          ("Most Queried Source Documents",    self.chart_top_sources),
        }

        result = {}
        for key, (title, fn) in charts.items():
            try:
                result[key] = {"title": title, "image": fn()}
            except Exception as e:
                logger.error(f"Chart '{key}' failed: {e}")
                result[key] = {"title": title, "image": None}
        return result
