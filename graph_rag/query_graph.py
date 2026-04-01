"""
query_graph.py — Interactive CLI for Graph RAG.

Usage:
  python query_graph.py              # interactive mode
  python query_graph.py --demo       # run 5 demo questions
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from graph_rag.retriever_graph import GraphRetriever

DEMO_QUESTIONS = [
    "What frameworks are used for competitive analysis?",
    "How does Porter's Five Forces relate to market entry strategy?",
    "What are the components of the McKinsey 7-S Framework?",
    "How is EBITDA used in valuation?",
    "What is the relationship between digital transformation and cloud computing?",
]


def main():
    parser = argparse.ArgumentParser(description="Graph RAG Query")
    parser.add_argument("--demo", action="store_true", help="Run demo questions")
    args = parser.parse_args()

    retriever = GraphRetriever()

    if args.demo:
        print("\nRunning Graph RAG demo questions...\n")
        for q in DEMO_QUESTIONS:
            retriever.ask(q)
            print()
    else:
        from naive_rag.retriever import rewrite_followup

        print("\nGraph RAG — Interactive Mode")
        print("Memory: last 15 turns  |  Type 'quit' to exit.\n")

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
    print("\nGraph RAG session ended.")


if __name__ == "__main__":
    main()
