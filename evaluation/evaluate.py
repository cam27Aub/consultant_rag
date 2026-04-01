#!/usr/bin/env python3
"""Consultant RAG evaluation runner.

Runs both evaluation phases:
  - Retrieval: Recall@K, Precision@K, MRR
  - Generation: Groundedness, Completeness, Relevancy

Also compares all 3 retrieval modes head-to-head.

Usage:
  python evaluate.py
  python evaluate.py --retrieval-only
  python evaluate.py --generation-only
  python evaluate.py --compare-modes
"""
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from naive_rag.retriever import RAGRetriever
from evaluation.evaluator import (
    RetrievalEvaluator, GenerationEvaluator, save_results, GOLDEN_DATASET
)
import config


def run_all(args):
    print("Loading RAG index...")
    retriever = RAGRetriever()
    stats = retriever.store.stats()
    print(f"{stats['total_chunks']} chunks loaded\n")

    results = {}

    if not args.generation_only:
        ret_eval = RetrievalEvaluator()
        ret_results = ret_eval.evaluate(retriever)
        results["retrieval"] = ret_results
        save_results(ret_results, "retrieval_eval")

    if not args.retrieval_only:
        gen_eval = GenerationEvaluator()
        gen_results = gen_eval.evaluate(retriever)
        results["generation"] = gen_results
        save_results(gen_results, "generation_eval")

    if args.compare_modes:
        print(f"\n{'═'*60}")
        print("  RETRIEVAL MODE COMPARISON")
        print("  vector vs. fulltext vs. hybrid (RRF)")
        print("═" * 60)

        mode_results = {}
        ret_eval = RetrievalEvaluator()

        for mode in ["vector", "fulltext", "hybrid"]:
            print(f"\n── Mode: {mode.upper()} ──")

            class _ModeRetriever:
                """Adapter that forces a specific retrieval mode."""
                def __init__(self, r, m):
                    self._r = r
                    self._m = m
                def retrieve(self, question, top_k=5, **kwargs):
                    return self._r.retrieve(question, mode=self._m, top_k=top_k)

            mode_retriever = _ModeRetriever(retriever, mode)
            mr = ret_eval.evaluate(mode_retriever)
            mode_results[mode] = mr["summary"]

        # Print comparison table
        print(f"\n{'─'*60}")
        print(f"  {'Metric':<20}  {'Vector':>8}  {'Fulltext':>10}  {'Hybrid':>8}")
        print(f"  {'─'*20}  {'─'*8}  {'─'*10}  {'─'*8}")
        all_keys = list(mode_results["vector"].keys())
        for key in all_keys:
            v = mode_results["vector"].get(key, 0)
            f = mode_results["fulltext"].get(key, 0)
            h = mode_results["hybrid"].get(key, 0)
            best = max(v, f, h)
            def fmt(x):
                return f"**{x:.3f}**" if x == best else f"  {x:.3f}  "
            print(f"  {key:<20}  {fmt(v):>10}  {fmt(f):>12}  {fmt(h):>10}")
        print("─" * 60)
        print("  ** = best score for that metric")

        results["mode_comparison"] = mode_results
        save_results(results, "full_evaluation")

    print(f"\n{'═'*60}")
    print("  EVALUATION COMPLETE")
    if "retrieval" in results:
        s = results["retrieval"]["summary"]
        print(f"  Retrieval  →  Recall@5={s.get('Recall@5', 0):.3f}  "
              f"MRR={s.get('MRR', 0):.3f}")
    if "generation" in results:
        s = results["generation"]["summary"]
        print(f"  Generation →  Groundedness={s['groundedness']:.3f}  "
              f"Completeness={s['completeness']:.3f}")
    print(f"  Results saved to: {config.EVAL_DIR}/")
    print("═" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrieval-only",   action="store_true")
    parser.add_argument("--generation-only",  action="store_true")
    parser.add_argument("--compare-modes",    action="store_true")
    args = parser.parse_args()
    run_all(args)
