"""
query_hybrid.py — Hybrid RAG query engine.

Strategy:
  1. Try Graph RAG first (entity + relationship traversal)
  2. If graph returns < MIN_NODES nodes OR confidence is low → fall back to Naive RAG
  3. If both return results → combine and let GPT-4o synthesise a unified answer

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

# how many graph nodes are needed before we trust the graph result alone
MIN_GRAPH_NODES = 3

HYBRID_PROMPT = """You are ConsultantIQ, an expert knowledge assistant for a management consulting firm.
You have been given two sources of information to answer the user's question:

1. GRAPH CONTEXT — entities and relationships extracted from documents
2. DOCUMENT CONTEXT — raw passages retrieved directly from documents

Rules:
1. Answer using ONLY the information contained in the GRAPH CONTEXT and DOCUMENT CONTEXT above. Do NOT use your general knowledge or training data.
2. If neither source contains the answer, say exactly: "I could not find this information in the knowledge base."
3. Do NOT infer, speculate, or fill gaps with outside knowledge. If the sources only partially cover the question, answer only the parts that are supported and state what is missing.
4. Cite source documents where relevant using: [Source: <filename>, <section>, Page <N>]
5. If the sources contradict each other, note it.
6. Be concise and professional. Use bullet points for lists of facts.

GRAPH CONTEXT:
{graph_context}

DOCUMENT CONTEXT:
{doc_context}

QUESTION: {question}
"""


class HybridRetriever:
    def __init__(self):
        self.graph = GraphRetriever()

        # load naive RAG retriever from parent folder
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

    def _get_naive_context(self, question: str) -> str:
        """Get raw passage context from naive RAG retriever."""
        if not self.naive:
            return ""
        try:
            chunks = self.naive.retrieve(question, top_k=5)
            if not chunks:
                return ""
            lines = []
            for i, c in enumerate(chunks, 1):
                if isinstance(c, dict):
                    text   = c.get("cleaned_text") or c.get("chunk_text") or ""
                    source = c.get("source", "")
                    page   = c.get("page", "")
                    section = c.get("section", "")
                else:
                    text   = getattr(c, "cleaned_text", "") or getattr(c, "chunk_text", "")
                    source = getattr(c, "source", "")
                    page   = getattr(c, "page", "")
                    section = getattr(c, "section", "")
                lines.append("[%d] %s | %s | p%s\n%s" % (i, source, section, page, text[:400]))
            return "\n\n".join(lines)
        except Exception as e:
            print("  Naive RAG retrieval failed: %s" % e)
            return ""

    def ask(self, question: str) -> str:
        print("\n" + "=" * 60)
        print("%s" % question)

        # Step 1 — Graph RAG retrieval
        subgraph = self.graph.retrieve(question, top_k=5)
        node_count = len(subgraph.get("nodes", []))
        graph_context = self.graph._build_context(subgraph)

        print("── Graph: %d nodes, %d edges" % (node_count, len(subgraph.get("edges", []))))

        # Step 2 — Naive RAG retrieval
        doc_context = self._get_naive_context(question)
        has_doc = bool(doc_context.strip())
        print("── Naive RAG: %s" % ("passages retrieved" if has_doc else "no results"))

        # Step 3 — Decide strategy
        if node_count >= MIN_GRAPH_NODES and has_doc:
            # Both sources available — synthesise
            mode = "HYBRID"
        elif node_count >= MIN_GRAPH_NODES:
            # Graph only
            mode = "GRAPH"
        elif has_doc:
            # Fall back to naive RAG
            mode = "NAIVE"
        else:
            print("── No results from either source")
            print("The knowledge base does not contain sufficient information to answer this question.")
            print("=" * 60)
            return "The knowledge base does not contain sufficient information to answer this question."

        print("── Mode: %s" % mode)

        # Step 4 — Generate answer
        if mode == "HYBRID":
            prompt = HYBRID_PROMPT.format(
                graph_context=graph_context,
                doc_context=doc_context,
                question=question,
            )
            response = self.llm.chat.completions.create(
                model=config.AZURE_CHAT_DEPLOYMENT,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=900,
            )
            answer = response.choices[0].message.content.strip()

        elif mode == "GRAPH":
            # use graph retriever's built-in generation
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.graph.ask(question)
            answer = buf.getvalue().strip()
            # clean up the terminal formatting lines
            lines = [l for l in answer.split("\n") if not l.startswith("=") and not l.startswith("──")]
            answer = "\n".join(lines).strip()

        else:  # NAIVE
            # call naive RAG ask() and capture output
            try:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    self.naive.ask(question)
                raw = buf.getvalue().strip()
                # strip the terminal formatting from query.py
                lines = [l for l in raw.split("\n") if not l.startswith("=") and not l.startswith("──") and not l.startswith("[")]
                answer = "\n".join(lines).strip()
            except Exception as e:
                answer = "Naive RAG error: %s" % e

        print(answer)
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
        print("\nRunning Hybrid RAG demo...\n")
        for q in DEMO_QUESTIONS:
            retriever.ask(q)
            print()
    else:
        from naive_rag.retriever import rewrite_followup

        print("\nHybrid RAG — Interactive Mode")
        print("Graph RAG + Naive RAG fallback")
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
    print("\nSession ended.")


if __name__ == "__main__":
    main()
