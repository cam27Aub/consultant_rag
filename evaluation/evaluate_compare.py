import sys
import argparse
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.evaluator import (
    RetrievalEvaluator, GenerationEvaluator, GOLDEN_DATASET, save_results
)
import config


def load_naive():
    from naive_rag.retriever import RAGRetriever
    r = RAGRetriever()
    print("  Naive RAG loaded (%d chunks)" % r.store.stats()["total_chunks"])
    return r


class GraphAdapter:
    """Wraps GraphRetriever to match the retrieve()/ask() interface."""
    def __init__(self):
        import asyncio, sys
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        from graph_rag.retriever_graph import GraphRetriever
        self._g = GraphRetriever()
        stats = self._g.store.stats()
        print("  Graph RAG loaded (%d nodes, %d edges)" % (
            stats["vertices"], stats["edges"]))

    def retrieve(self, question, top_k=5):
        subgraph = self._g.retrieve(question, top_k=top_k)
        # convert nodes to chunk-like dicts for evaluator compatibility
        return [
            {
                "source":      n.get("source", ""),
                "chunk_text":  "%s: %s" % (n.get("name", ""), n.get("description", "")),
                "cleaned_text":"%s: %s" % (n.get("name", ""), n.get("description", "")),
                "page":        n.get("page", 0),
                "section":     n.get("name", ""),
            }
            for n in subgraph.get("nodes", [])
        ]

    def ask(self, question):
        return self._g.ask(question)

    def close(self):
        self._g.close()


class HybridAdapter:
    def __init__(self):
        import asyncio, sys
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        from hybrid_rag.query_hybrid import HybridRetriever
        self._h = HybridRetriever()
        print("  Hybrid RAG loaded")

    def retrieve(self, question, top_k=5):
        # combine graph nodes + naive chunks
        graph_chunks = []
        naive_chunks = []
        try:
            subgraph = self._h.graph.retrieve(question, top_k=top_k)
            graph_chunks = [
                {
                    "source":      n.get("source", ""),
                    "chunk_text":  "%s: %s" % (n.get("name",""), n.get("description","")),
                    "cleaned_text":"%s: %s" % (n.get("name",""), n.get("description","")),
                    "page":        n.get("page", 0),
                }
                for n in subgraph.get("nodes", [])
            ]
        except Exception:
            pass
        try:
            naive_chunks = self._h.naive.retrieve(question, top_k=top_k) or []
        except Exception:
            pass
        return (graph_chunks + naive_chunks)[:top_k]

    def ask(self, question):
        return self._h.ask(question)

    def close(self):
        self._h.close()


def evaluate_system(name, retriever, ret_eval, gen_eval,
                    do_retrieval=True, do_generation=True):
    print("\n%s" % ("═" * 60))
    print("  EVALUATING: %s" % name.upper())
    print("═" * 60)
    results = {"system": name}

    if do_retrieval:
        print("\n── Retrieval Metrics ──")
        results["retrieval"] = ret_eval.evaluate(retriever)

    if do_generation:
        print("\n── Generation Metrics ──")
        results["generation"] = gen_eval.evaluate(retriever)

    return results


def print_comparison_table(all_results, do_retrieval, do_generation):
    print("\n%s" % ("═" * 70))
    print("  COMPARISON SUMMARY")
    print("═" * 70)

    systems = [r["system"] for r in all_results]
    header  = "  %-22s" % "Metric"
    for s in systems:
        header += "  %10s" % s[:10]
    print(header)
    print("  " + "─" * 68)

    metrics = []
    if do_retrieval:
        metrics += ["Recall@1", "Recall@3", "Recall@5",
                    "Precision@1", "Precision@5", "MRR"]
    if do_generation:
        metrics += ["groundedness", "completeness", "relevancy"]

    for metric in metrics:
        row = "  %-22s" % metric
        vals = []
        for r in all_results:
            if metric in ["groundedness", "completeness", "relevancy"]:
                v = r.get("generation", {}).get("summary", {}).get(metric, None)
            else:
                v = r.get("retrieval", {}).get("summary", {}).get(metric, None)
            vals.append(v)

        best = max((v for v in vals if v is not None), default=None)
        for v in vals:
            if v is None:
                row += "  %10s" % "N/A"
            elif v == best:
                row += "  %9.3f*" % v
            else:
                row += "  %10.3f" % v
        print(row)

    print("  " + "─" * 68)
    print("  * = best score for that metric")
    print("═" * 70)


def main():
    parser = argparse.ArgumentParser(description="RAG Evaluation Comparison")
    parser.add_argument("--retrieval-only",  action="store_true")
    parser.add_argument("--generation-only", action="store_true")
    parser.add_argument("--system", choices=["naive","graph","hybrid","all"],
                        default="all", help="Which system to evaluate")
    args = parser.parse_args()

    do_retrieval  = not args.generation_only
    do_generation = not args.retrieval_only

    ret_eval = RetrievalEvaluator()
    gen_eval = GenerationEvaluator()

    systems_to_run = {
        "naive":  load_naive,
        "graph":  GraphAdapter,
        "hybrid": HybridAdapter,
    }

    if args.system != "all":
        systems_to_run = {args.system: systems_to_run[args.system]}

    all_results = []
    for name, loader in systems_to_run.items():
        print("\nLoading %s..." % name)
        try:
            retriever = loader() if callable(loader) and not isinstance(loader, type) else loader()
            result    = evaluate_system(
                name, retriever, ret_eval, gen_eval,
                do_retrieval=do_retrieval,
                do_generation=do_generation,
            )
            all_results.append(result)
            if hasattr(retriever, "close"):
                retriever.close()
        except Exception as e:
            print("  %s failed to load: %s" % (name, e))

    if len(all_results) > 1:
        print_comparison_table(all_results, do_retrieval, do_generation)

    # save
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(config.EVAL_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / ("comparison_%s.json" % ts)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print("\n  Full results saved -> %s" % out_path)


if __name__ == "__main__":
    main()
