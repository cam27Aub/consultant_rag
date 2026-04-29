"""
query_hybrid.py — Smart RAG router.

Strategy:
  1. GPT-4o classifies the query as GRAPH or NAIVE
  2. Only the selected retriever runs — no parallel execution
  3. Returns a single grounded answer

  GRAPH  → entity/relationship questions (how X connects to Y, what firms use Z)
  NAIVE  → factual/passage questions (what is X, list the steps of Y)

Usage:
  python query_hybrid.py              # interactive mode
  python query_hybrid.py --demo       # run demo questions
"""
import asyncio, sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import sys
import io
import contextlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from graph_rag.retriever_graph import GraphRetriever
from graph_rag import config_graph as config
from openai import AzureOpenAI

# ── Classifier prompt ────────────────────────────────────────────────────────
_CLASSIFIER_PROMPT = """You are a query router for a RAG system that has two retrieval engines:

GRAPH  — best for questions about relationships, connections, and how concepts/entities relate to each other.
         Use GRAPH when the question asks how X connects to Y, what links two concepts, or how entities interact.
         Examples: "How does IT-OT convergence relate to industrial automation?",
                   "What is the relationship between orchestration layer and data layer?",
                   "How does MCP protocol connect AI agents to enterprise tools?"

NAIVE  — best for factual, statistical, definition, or passage-level questions.
         Use NAIVE when the question asks for specific numbers, percentages, market sizes, definitions,
         lists of steps, or any answer that would come from a specific passage in a document.
         Examples: "What productivity gains can manufacturers expect from AI-enabled automation?",
                   "What share of airline revenues will flow through AI by 2030?",
                   "What are the three layers of Bain's agentic AI platform?",
                   "How productive are MSMEs compared to large companies?",
                   "What are the main barriers to productivity growth?"

When in doubt, choose NAIVE.

Given the query below, respond with exactly one word: GRAPH or NAIVE.

Query: {question}"""


class HybridRetriever:
    def __init__(self):
        self.graph = GraphRetriever()

        try:
            from naive_rag.retriever import RAGRetriever
            self.naive = RAGRetriever()
            print("  Naive RAG loaded")
        except Exception as e:
            self.naive = None
            print("  Naive RAG not available: %s" % e)

        self.llm = AzureOpenAI(
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
            api_key=config.AZURE_OPENAI_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
        )

    def _classify(self, question: str) -> str:
        """Ask GPT-4o to classify the query as GRAPH or NAIVE."""
        try:
            response = self.llm.chat.completions.create(
                model=config.AZURE_CHAT_DEPLOYMENT,
                messages=[{
                    "role": "user",
                    "content": _CLASSIFIER_PROMPT.format(question=question)
                }],
                temperature=0,
                max_tokens=5,
            )
            decision = response.choices[0].message.content.strip().upper()
            return "graph" if "GRAPH" in decision else "naive"
        except Exception as e:
            print("  Classifier error: %s — defaulting to naive" % e)
            return "naive"

    def _run_graph(self, question: str) -> str:
        """Run Graph RAG and return the answer."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.graph.ask(question)
        raw = buf.getvalue().strip()
        lines = [l for l in raw.split("\n")
                 if not l.startswith("=") and not l.startswith("──")]
        return "\n".join(lines).strip()

    def _run_naive(self, question: str) -> str:
        """Run Naive RAG and return the answer."""
        if not self.naive:
            return "Naive RAG not available."
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.naive.ask(question)
            raw = buf.getvalue().strip()
            lines = [l for l in raw.split("\n")
                     if not l.startswith("=") and not l.startswith("──")
                     and not l.startswith("[")]
            return "\n".join(lines).strip()
        except Exception as e:
            return "Naive RAG error: %s" % e

    def ask(self, question: str) -> str:
        print("\n" + "=" * 60)
        print("%s" % question)

        # Step 1 — Classify query
        mode = self._classify(question)
        print("── Mode: %s" % mode.upper())

        # Step 2 — Run only the selected retriever
        _graph_failures = (
            "no relevant entities", "cannot answer", "subgraph contains no",
            "not contain", "no information", "insufficient",
        )
        if mode == "graph":
            answer = self._run_graph(question)
            # fallback to naive if graph returns nothing useful or an explicit failure
            if not answer or len(answer) < 30 or any(f in answer.lower() for f in _graph_failures):
                print("── Graph returned no results — falling back to naive")
                mode = "naive"
                answer = self._run_naive(question)
        else:
            answer = self._run_naive(question)
            # fallback to graph if naive returns nothing useful
            if not answer or len(answer) < 30:
                print("── Naive returned no results — falling back to graph")
                mode = "graph"
                answer = self._run_graph(question)

        if not answer or len(answer) < 30:
            answer = "The knowledge base does not contain sufficient information to answer this question."

        print(answer)
        print("── Final mode: %s" % mode.upper())
        print("=" * 60)
        return answer

    def close(self):
        self.graph.close()


DEMO_QUESTIONS = [
    "What are the steps of the Big Data Value Chain?",
    "How does Porter's Five Forces connect to market entry strategy?",
    "What is the solution to the appraisal in data curation?",
    "What determines AI model behavior?",
    "How is EBITDA used in valuation?",
]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    retriever = HybridRetriever()

    if args.demo:
        print("\nRunning Smart RAG Router demo...\n")
        for q in DEMO_QUESTIONS:
            retriever.ask(q)
            print()
    else:
        from naive_rag.retriever import rewrite_followup

        print("\nSmart RAG Router — Interactive Mode")
        print("GPT classifies each query → runs Graph RAG or Naive RAG")
        print("Type 'quit' to exit.\n")

        conversation = []

        while True:
            try:
                question = input("? ").strip()
                if question.lower() in ("quit", "exit", "q"):
                    break
                if not question:
                    continue

                rewrite = rewrite_followup(question, conversation[-30:])
                effective_q = rewrite["rewritten"]
                if rewrite["is_followup"]:
                    print(f"  [rewritten → {effective_q}]")

                answer = retriever.ask(effective_q)

                conversation.append({"role": "user", "content": question})
                conversation.append({"role": "assistant", "content": answer if isinstance(answer, str) else ""})
                print()
            except KeyboardInterrupt:
                break

    retriever.close()
    print("\nSession ended.")


if __name__ == "__main__":
    main()
