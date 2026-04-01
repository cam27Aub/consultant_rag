import json
import math
import os
import re
from pathlib import Path
from datetime import datetime

GOLDEN_DATASET = [
    {
        "question": "What are Porter's Five Forces and how should consultants use them?",
        "relevant_sources": ["strategic_frameworks_guide.docx"],
        "expected_answer": "Porter's Five Forces is a framework for competitive analysis covering threat of new entrants, bargaining power of suppliers, bargaining power of buyers, threat of substitutes, and competitive rivalry. Consultants rate each force as Low, Medium, or High.",
        "keywords": ["new entrants", "suppliers", "buyers", "substitutes", "rivalry", "competitive", "industry"]
    },
    {
        "question": "What are the four quadrants of the BCG Growth-Share Matrix?",
        "relevant_sources": ["strategic_frameworks_guide.docx"],
        "expected_answer": "The four quadrants are Stars (high growth, high share), Cash Cows (low growth, high share), Question Marks (high growth, low share), and Dogs (low growth, low share).",
        "keywords": ["stars", "cash cows", "question marks", "dogs", "growth", "market share"]
    },
    {
        "question": "What is the MECE principle in consulting?",
        "relevant_sources": ["strategic_frameworks_guide.docx"],
        "expected_answer": "MECE stands for Mutually Exclusive Collectively Exhaustive. It ensures problem decomposition is both complete and non-overlapping, enabling teams to divide work streams efficiently.",
        "keywords": ["mutually exclusive", "collectively exhaustive", "issue tree", "problem", "decomposition"]
    },
    {
        "question": "What are the primary activities in Porter's Value Chain?",
        "relevant_sources": ["strategic_frameworks_guide.docx"],
        "expected_answer": "The primary activities are inbound logistics, operations, outbound logistics, marketing and sales, and service.",
        "keywords": ["inbound logistics", "operations", "outbound logistics", "marketing", "service"]
    },
    {
        "question": "What are the main reasons digital transformation programs fail?",
        "relevant_sources": ["digital_transformation_playbook.pdf"],
        "expected_answer": "Digital transformation programs fail primarily due to organizational reasons: lack of clear vision, insufficient executive sponsorship, resistance to change, talent gaps, and poor program governance. The failure rate is 60 to 80 percent.",
        "keywords": ["vision", "sponsorship", "resistance", "talent", "governance", "failure", "60", "80"]
    },
    {
        "question": "What are the four pillars of digital transformation?",
        "relevant_sources": ["digital_transformation_playbook.pdf"],
        "expected_answer": "The four pillars are Customer Experience, Operational Efficiency, Business Model Innovation, and Data and Analytics.",
        "keywords": ["customer experience", "operational efficiency", "business model", "data", "analytics"]
    },
    {
        "question": "How should a digital transformation roadmap be designed?",
        "relevant_sources": ["digital_transformation_playbook.pdf"],
        "expected_answer": "The roadmap should start with value not technology, sequence for dependencies and quick wins, right-size the portfolio to three to five initiatives, build in governance and decision gates, and allocate 15 to 20 percent of budget to change management.",
        "keywords": ["value", "quick wins", "portfolio", "governance", "change management", "sequence"]
    },
    {
        "question": "What is EBITDA and why do consultants use it?",
        "relevant_sources": ["financial_analysis_toolkit.pdf"],
        "expected_answer": "EBITDA is earnings before interest, taxes, depreciation, and amortization. Consultants use it because it strips out effects of capital structure, tax jurisdiction, and accounting policies enabling cleaner comparisons across companies and industries.",
        "keywords": ["earnings", "interest", "depreciation", "amortization", "capital structure", "comparison"]
    },
    {
        "question": "What are the three valuation methodologies used in consulting?",
        "relevant_sources": ["financial_analysis_toolkit.pdf"],
        "expected_answer": "The three methodologies are Discounted Cash Flow (DCF) analysis, Comparable Company Analysis using trading multiples, and Precedent Transactions Analysis.",
        "keywords": ["discounted cash flow", "DCF", "comparable company", "trading multiples", "precedent transactions"]
    },
    {
        "question": "What is the pyramid principle in consulting communication?",
        "relevant_sources": ["client_engagement_best_practices.docx"],
        "expected_answer": "The pyramid principle developed by Barbara Minto at McKinsey states that you should lead with the answer, then support it with grouped and summarized arguments, and finally provide detailed evidence.",
        "keywords": ["pyramid", "Minto", "answer", "argument", "evidence", "lead", "McKinsey"]
    },
    {
        "question": "How should stakeholders be managed during a consulting engagement?",
        "relevant_sources": ["client_engagement_best_practices.docx"],
        "expected_answer": "Stakeholders include sponsors, key decision-makers, subject matter experts, potential blockers, and implementation owners. Each requires a different management approach including keeping sponsors informed, pre-wiring recommendations with decision-makers, and engaging blockers early.",
        "keywords": ["sponsor", "decision-maker", "blocker", "subject matter expert", "implementation", "engagement"]
    },
    {
        "question": "What financial modeling best practices should consultants follow?",
        "relevant_sources": ["financial_analysis_toolkit.pdf"],
        "expected_answer": "Best practices include separating inputs from calculations from outputs, using color coding with blue for inputs and black for calculations, including base case upside and downside scenarios, avoiding circular references and hardcoded numbers, and building in error checks.",
        "keywords": ["inputs", "calculations", "scenario", "base case", "circular", "assumptions", "color"]
    },
]


def _word_overlap(a: str, b: str) -> float:
    """Simple token-level Jaccard overlap between two strings."""
    ta = set(re.findall(r"\w+", a.lower()))
    tb = set(re.findall(r"\w+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _tfidf_cosine(a: str, b: str) -> float:
    """
    Lightweight TF-IDF cosine similarity without sklearn dependency.
    """
    def tf(text):
        words = re.findall(r"\w+", text.lower())
        freq = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        total = len(words) or 1
        return {w: c / total for w, c in freq.items()}

    ta, tb = tf(a), tf(b)
    vocab = set(ta) | set(tb)
    dot = sum(ta.get(w, 0) * tb.get(w, 0) for w in vocab)
    na  = math.sqrt(sum(v**2 for v in ta.values()))
    nb  = math.sqrt(sum(v**2 for v in tb.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class RetrievalEvaluator:

    def recall_at_k(self, retrieved: list, relevant_sources: list, k: int) -> float:
        top_k   = retrieved[:k]
        sources = set()
        for c in top_k:
            src = c.get("source", "") if isinstance(c, dict) else getattr(c, "source", "")
            sources.add(src)
        hits = sum(1 for r in relevant_sources if any(r in s for s in sources))
        return hits / len(relevant_sources) if relevant_sources else 0.0

    def precision_at_k(self, retrieved: list, relevant_sources: list, k: int) -> float:
        top_k = retrieved[:k]
        hits  = 0
        for c in top_k:
            src = c.get("source", "") if isinstance(c, dict) else getattr(c, "source", "")
            if any(r in src for r in relevant_sources):
                hits += 1
        return hits / k if k else 0.0

    def reciprocal_rank(self, retrieved: list, relevant_sources: list) -> float:
        for rank, c in enumerate(retrieved, 1):
            src = c.get("source", "") if isinstance(c, dict) else getattr(c, "source", "")
            if any(r in src for r in relevant_sources):
                return 1.0 / rank
        return 0.0

    def evaluate(self, retriever, k_values: list = None) -> dict:
        if k_values is None:
            k_values = [1, 3, 5]

        per_query = []
        for item in GOLDEN_DATASET:
            q       = item["question"]
            sources = item["relevant_sources"]
            try:
                chunks = retriever.retrieve(q, top_k=max(k_values))
            except Exception as e:
                print("  Retrieval failed for: %s -- %s" % (q[:50], e))
                chunks = []

            row = {"question": q}
            for k in k_values:
                row["Recall@%d"    % k] = self.recall_at_k(chunks, sources, k)
                row["Precision@%d" % k] = self.precision_at_k(chunks, sources, k)
            row["MRR"] = self.reciprocal_rank(chunks, sources)
            per_query.append(row)
            print("  %s... R@5=%.2f MRR=%.2f" % (q[:45], row.get("Recall@5", 0), row["MRR"]))

        # aggregate
        summary = {}
        keys = [k for k in per_query[0] if k != "question"]
        for key in keys:
            summary[key] = sum(r[key] for r in per_query) / len(per_query)

        print("\n  Retrieval Summary:")
        for k, v in summary.items():
            print("     %-18s %.3f" % (k, v))

        return {"per_query": per_query, "summary": summary}


class GenerationEvaluator:

    def groundedness(self, answer: str, chunks: list) -> float:
        """
        Fraction of answer sentences that are lexically supported
        by at least one retrieved chunk.
        """
        sentences = [s.strip() for s in re.split(r"[.!?]", answer) if len(s.strip()) > 10]
        if not sentences:
            return 0.0
        context = " ".join(
            (c.get("cleaned_text") or c.get("chunk_text") or "") if isinstance(c, dict)
            else (getattr(c, "cleaned_text", "") or getattr(c, "chunk_text", ""))
            for c in chunks
        )
        supported = sum(1 for s in sentences if _word_overlap(s, context) > 0.08)
        return supported / len(sentences)

    def completeness(self, answer: str, expected_keywords: list) -> float:
        """Fraction of expected keywords present in the answer."""
        if not expected_keywords:
            return 0.0
        answer_lower = answer.lower()
        hits = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
        return hits / len(expected_keywords)

    def relevancy(self, answer: str, question: str) -> float:
        """TF-IDF cosine similarity between question and answer."""
        return _tfidf_cosine(question, answer)

    def evaluate(self, retriever) -> dict:
        per_query = []
        for item in GOLDEN_DATASET:
            q        = item["question"]
            keywords = item["keywords"]
            try:
                chunks = retriever.retrieve(q, top_k=5)
                import io, contextlib
                # capture stdout to get the printed answer
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    result = retriever.ask(q)
                captured = buf.getvalue().strip()
                # prefer a returned string over stdout capture
                if isinstance(result, str) and len(result) > 20:
                    answer = result
                else:
                    answer = captured
                # strip terminal formatting lines
                lines = []
                for l in answer.split("\n"):
                    stripped = l.strip()
                    if (stripped.startswith("=") or stripped.startswith("❓")
                            or stripped.startswith("──") or stripped.startswith("[")
                            or stripped.startswith("🔑") or stripped.startswith("🌐")
                            or stripped.startswith("──") or len(stripped) < 2):
                        continue
                    lines.append(l)
                answer = "\n".join(lines).strip()
            except Exception as e:
                print("  Generation failed for: %s -- %s" % (q[:50], e))
                chunks, answer = [], ""

            row = {
                "question":     q,
                "groundedness": self.groundedness(answer, chunks),
                "completeness": self.completeness(answer, keywords),
                "relevancy":    self.relevancy(answer, q),
                "answer":       answer[:300],
            }
            per_query.append(row)
            print("  %s... G=%.2f C=%.2f R=%.2f" % (
                q[:40], row["groundedness"], row["completeness"], row["relevancy"]))

        summary = {
            "groundedness": sum(r["groundedness"] for r in per_query) / len(per_query),
            "completeness": sum(r["completeness"] for r in per_query) / len(per_query),
            "relevancy":    sum(r["relevancy"]    for r in per_query) / len(per_query),
        }

        print("\n  Generation Summary:")
        for k, v in summary.items():
            print("     %-18s %.3f" % (k, v))

        return {"per_query": per_query, "summary": summary}


def save_results(results: dict, name: str):
    import config
    out_dir = Path(config.EVAL_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / ("%s_%s.json" % (name, ts))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("  Results saved -> %s" % path)
