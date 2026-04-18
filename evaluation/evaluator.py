import json
import math
import os
import re
from pathlib import Path
from datetime import datetime

GOLDEN_DATASET = [
    {
        "question": "What percentage of the time do large language models direct users to airline websites when asked about flights?",
        "relevant_sources": ["bain_brief_is_the_airline_industry_ready_for_agent-led_bookings.pdf"],
        "expected_answer": "Large language models direct users to airline websites only about 5 percent of the time. The top 6 online travel agencies account for approximately 67 percent of LLM-driven search traffic.",
        "keywords": ["5%", "OTA", "airline", "LLM", "online travel", "67"]
    },
    {
        "question": "What are the three layers of the agentic AI platform architecture described by Bain?",
        "relevant_sources": ["Layers of Agentic AI by Bain.pdf"],
        "expected_answer": "The three layers are the Application and Orchestration layer, the Analytics and Insight layer, and the Data and Knowledge layer.",
        "keywords": ["orchestration", "analytics", "insight", "data", "knowledge", "application", "layer"]
    },
    {
        "question": "How productive are MSMEs compared to large companies on average?",
        "relevant_sources": ["a-microscope-on-small-businesses-spotting-opportunities-to-boost-productivity.pdf"],
        "expected_answer": "MSMEs are roughly half as productive as large companies on average. Closing this gap could add 5 percent to GDP in advanced economies and 10 percent in emerging markets.",
        "keywords": ["half", "productive", "5%", "10%", "GDP", "advanced", "emerging"]
    },
    {
        "question": "What is the projected industrial automation market size by 2030 and how much new AI value will be unlocked?",
        "relevant_sources": ["bain_brief_industrial_automation_from_control_to__intelligence.pdf"],
        "expected_answer": "The industrial automation market is projected to grow from 250 billion dollars in 2025 to 400 billion dollars by 2030. An additional 70 billion dollars of new AI market value is expected to be unlocked by 2030.",
        "keywords": ["250", "400", "70", "billion", "2030", "AI", "market"]
    },
    {
        "question": "How does the MSME productivity gap differ between B2B and B2C businesses?",
        "relevant_sources": ["a-microscope-on-small-businesses-spotting-opportunities-to-boost-productivity.pdf"],
        "expected_answer": "B2B MSMEs have a 40 percent narrower productivity gap compared to B2C MSMEs. B2B MSMEs are also 30 percent more likely to introduce process innovation and provide formal training to 60 percent of employees versus 35 percent at B2C MSMEs.",
        "keywords": ["40%", "B2B", "B2C", "narrower", "innovation", "training", "60%", "35%"]
    },
    {
        "question": "What is the total annual economic value that generative AI could add to the global economy?",
        "relevant_sources": ["the-economic-potential-of-generative-ai-the-next-productivity-frontier.pdf"],
        "expected_answer": "Generative AI could add between 2.6 trillion and 4.4 trillion dollars annually across the use cases analyzed by McKinsey.",
        "keywords": ["2.6", "4.4", "trillion", "annually", "economic", "generative AI"]
    },
    {
        "question": "What productivity and maintenance cost gains can manufacturers expect from AI-enabled industrial automation?",
        "relevant_sources": ["bain_brief_industrial_automation_from_control_to__intelligence.pdf"],
        "expected_answer": "Manufacturers can expect 30 to 50 percent productivity gains and up to 35 percent maintenance cost reductions from AI-enabled industrial automation.",
        "keywords": ["30", "50", "productivity", "35", "maintenance", "cost", "reduction"]
    },
    {
        "question": "How do AI agents discover tools in a modern agentic AI platform?",
        "relevant_sources": ["Layers of Agentic AI by Bain.pdf"],
        "expected_answer": "AI agents discover and connect to tools via MCP (Model Context Protocol) servers and tool catalogs, enabling dynamic tool discovery rather than static API endpoint configuration.",
        "keywords": ["MCP", "Model Context Protocol", "tool catalog", "discovery", "agents"]
    },
    {
        "question": "What is friend-shoring and how is it reshaping global supply chains?",
        "relevant_sources": ["geopolitics-and-the-geometry-of-global-trade-vf.pdf"],
        "expected_answer": "Friend-shoring involves relocating supply chains to geopolitically aligned countries, prioritizing security and reliability over pure cost efficiency. It is part of a broader shift away from globally optimized supply chains toward geopolitically resilient ones.",
        "keywords": ["friend-shoring", "geopolitical", "supply chain", "aligned", "security", "resilient"]
    },
    {
        "question": "What are the AI substitution rates for manufacturing operations management and sensor roles?",
        "relevant_sources": ["bain_brief_industrial_automation_from_control_to__intelligence.pdf"],
        "expected_answer": "The AI substitution rate for manufacturing operations management is 55 percent, manufacturing monitoring is 54 percent, manufacturing control is 54 percent, maintenance is 51 percent, and sensors have a lower substitution rate of 24 percent.",
        "keywords": ["55", "54", "51", "24", "substitution", "manufacturing", "operations", "sensors"]
    },
    {
        "question": "What share of airline industry revenues is expected to flow through AI-based solutions by 2030?",
        "relevant_sources": ["bain_brief_is_the_airline_industry_ready_for_agent-led_bookings.pdf"],
        "expected_answer": "Nearly half of airline industry revenues are projected to pass through AI-based solutions by 2030.",
        "keywords": ["half", "revenues", "2030", "AI", "airline", "agent"]
    },
    {
        "question": "What are the main barriers to productivity growth in advanced economies?",
        "relevant_sources": ["investing-in-productivity-growth-vf.pdf"],
        "expected_answer": "Key barriers include capital misallocation, regulatory burden, low research and development investment, and slow technology diffusion from frontier firms to laggard firms.",
        "keywords": ["capital", "misallocation", "regulatory", "R&D", "technology diffusion", "frontier", "laggard"]
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
