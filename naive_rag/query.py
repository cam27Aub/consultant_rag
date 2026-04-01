#!/usr/bin/env python3
"""Consultant RAG - Query Interface.

Usage:
    python query.py                              # interactive
    python query.py --q "What are EBITDA margins?"
    python query.py --mode vector
    python query.py --mode fulltext
    python query.py --compare                    # compare all 3 modes
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from naive_rag.retriever import RAGRetriever
import config


DEMO_QUESTIONS = [
    "What are the average EBITDA margins for retail companies in 2024?",
    "Which retail sub-sector has the highest EBITDA margin?",
    "What is the hotel allowance for Tier 1 cities like London?",
    "What is the recommended market entry strategy for Saudi Arabia?",
    "What are the 5 dimensions in the digital maturity model?",
    "What is the daily meal allowance cap for consultants?",
    "What are the main margin improvement levers for retail?",
    "What is the UAE consumer goods market size?",
]


def compare_modes(retriever: RAGRetriever, question: str):
    """Run same question through all 3 retrieval modes and compare."""
    print(f"\n{'═'*60}")
    print(f"RETRIEVAL MODE COMPARISON")
    print(f"  {question}")
    print("═" * 60)

    for mode in ["vector", "fulltext", "hybrid"]:
        print(f"\n── Mode: {mode.upper()} ──────────────────────────────────")
        chunks = retriever.retrieve(question, mode=mode, top_k=3)
        for i, c in enumerate(chunks):
            score_key = "_score_rrf" if mode == "hybrid" else (
                "_score_vector" if mode == "vector" else "_score_fulltext"
            )
            score = c.get(score_key, 0)
            print(f"  [{i+1}] {c['source'][:35]} | {c.get('section','')[:30]} "
                  f"| score={score:.4f}")

    print("\n── HYBRID ANSWER ────────────────────────────────────────")
    result = retriever.ask(question, mode="hybrid", verbose=False)
    print(result["answer"])
    print("═" * 60)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--q",       default=None,    help="Single question")
    parser.add_argument("--mode",    default=None,    choices=["vector", "fulltext", "hybrid"])
    parser.add_argument("--demo",    action="store_true", help="Run all demo questions")
    parser.add_argument("--compare", action="store_true", help="Compare retrieval modes")
    args = parser.parse_args()

    print("Loading RAG index...")
    retriever = RAGRetriever()
    stats = retriever.store.stats()
    print(f"Loaded {stats['total_chunks']} chunks from {len(stats['sources'])} documents\n")

    if args.q and args.compare:
        compare_modes(retriever, args.q)

    elif args.q:
        retriever.ask(args.q, mode=args.mode, verbose=True)

    elif args.demo:
        for q in DEMO_QUESTIONS:
            retriever.ask(q, verbose=True)
            import time; time.sleep(0.2)

    else:
        # Interactive mode with conversation memory
        from naive_rag.retriever import rewrite_followup

        print("ConsultantIQ — RAG Query Interface")
        print("Memory: last 15 turns  |  Commands:  'demo' | 'compare' | 'quit'")
        print("─" * 40)

        conversation = []

        while True:
            try:
                user_input = input("\nYour question: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break
            if user_input.lower() == "demo":
                for q in DEMO_QUESTIONS[:3]:
                    retriever.ask(q, verbose=True)
                    import time; time.sleep(0.1)
            elif user_input.lower() == "compare":
                q = input("  Question to compare: ").strip()
                if q:
                    compare_modes(retriever, q)
            else:
                # Rewrite follow-ups using conversation memory
                rewrite = rewrite_followup(user_input, conversation[-30:])
                effective_q = rewrite["rewritten"]
                if rewrite["is_followup"]:
                    print(f"  [rewritten → {effective_q}]")

                retriever.ask(effective_q, verbose=True)

                # Store turn in memory
                conversation.append({"role": "user", "content": user_input})
                conversation.append({"role": "assistant", "content": effective_q})


if __name__ == "__main__":
    main()
