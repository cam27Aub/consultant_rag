import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from store.vector_store import get_store
from pipeline.embedder import load_embedder
import config


SYSTEM_PROMPT = """You are ConsultantIQ, an expert knowledge assistant for a management consulting firm.
Answer questions using ONLY the context documents provided. Do NOT use general knowledge.

Rules:
1. Base every claim strictly on the provided context documents. NEVER fabricate information or add claims not supported by the context.
2. IMPORTANT: If the context discusses the topic being asked about (even if it does not address the exact question), you MUST provide a response using the available information. Explain what the documents say about the topic and clearly note which specific aspects of the question are not directly covered.
3. Only say "I could not find this information in the knowledge base." if the context is completely unrelated to the question topic.
4. Always cite your sources at the end using: [Source: <filename>, <section>, Page/Slide <N>]
5. Be concise and professional. Use bullet points for lists of facts.
6. When citing numbers or statistics, always include the source inline.
"""

REWRITE_PROMPT = """You are a query rewriter for a RAG system.

Given the recent conversation history and the user's latest question, decide:
- Is the latest question a follow-up that depends on prior context?
- If YES, rewrite it into a fully self-contained question that a retrieval engine can answer without seeing the conversation.
- If NO, return the question unchanged.

Return ONLY valid JSON (no markdown, no explanation):
{
  "is_followup": true/false,
  "rewritten": "<the self-contained question>"
}

CONVERSATION HISTORY:
{history}

LATEST QUESTION: {question}"""


def _azure_answer(question: str, chunks: list[dict]) -> str:
    from openai import AzureOpenAI
    client = AzureOpenAI(
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
        api_key=config.AZURE_OPENAI_KEY,
        api_version=config.AZURE_OPENAI_API_VERSION,
    )
    context_parts = []
    for i, c in enumerate(chunks):
        context_parts.append(
            f"[Doc {i+1}] Source: {c['source']}, "
            f"Section: {c.get('section','')}, "
            f"Page/Slide: {c.get('page','?')}\n"
            f"{c.get('cleaned_text') or c.get('chunk_text','')}"
        )
    context = "\n\n---\n\n".join(context_parts)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": f"CONTEXT:\n\n{context}\n\n---\n\nQUESTION: {question}"}
    ]
    response = client.chat.completions.create(
        model=config.AZURE_CHAT_DEPLOYMENT,
        messages=messages,
        temperature=0.1,
        max_tokens=800,
    )
    return response.choices[0].message.content


def _extractive_answer(question: str, chunks: list[dict]) -> str:
    q_words = set(re.findall(r'\b\w{4,}\b', question.lower()))
    scored = []
    for chunk in chunks:
        text   = chunk.get("cleaned_text") or chunk.get("chunk_text", "")
        source = chunk.get("source", "")
        section= chunk.get("section", "")
        page   = chunk.get("page", "?")
        for sent in re.split(r'(?<=[.!?])\s+', text):
            if len(sent.split()) < 6:
                continue
            sw = set(re.findall(r'\b\w{4,}\b', sent.lower()))
            overlap = len(q_words & sw)
            if overlap > 0:
                scored.append((overlap, sent, source, section, page))
    if not scored:
        return "I could not find specific information about this in the knowledge base."
    scored.sort(key=lambda x: -x[0])
    selected = []
    seen = set()
    for score, sent, source, section, page in scored:
        sw = set(sent.lower().split())
        if len(sw & seen) / max(len(sw), 1) < 0.5:
            selected.append((sent, source, section, page))
            seen |= sw
        if len(selected) >= 5:
            break
    lines = ["**Based on the knowledge base:**\n"]
    citations = []
    for sent, source, section, page in selected:
        lines.append(f"• {sent}")
        cite = f"[Source: {source}, {section}, Page/Slide {page}]"
        if cite not in citations:
            citations.append(cite)
    lines.append("\n**Citations:**")
    lines.extend(citations)
    return "\n".join(lines)


def rewrite_followup(question: str, conversation: list[dict]) -> dict:
    """
    Check if *question* is a follow-up and rewrite it to be self-contained.

    Parameters
    ----------
    question : str
        The user's raw question.
    conversation : list[dict]
        Rolling window of previous turns, each with 'role' and 'content'.

    Returns
    -------
    dict  {"rewritten": str, "is_followup": bool, "used_memory": bool}
    """
    if not conversation:
        return {"rewritten": question, "is_followup": False, "used_memory": False}

    # Build a compact history string
    history_lines = []
    for turn in conversation:
        role = "User" if turn["role"] == "user" else "Assistant"
        text = turn["content"][:300]
        history_lines.append(f"{role}: {text}")
    history_text = "\n".join(history_lines)

    import json
    from openai import AzureOpenAI
    client = AzureOpenAI(
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
        api_key=config.AZURE_OPENAI_KEY,
        api_version=config.AZURE_OPENAI_API_VERSION,
    )
    try:
        resp = client.chat.completions.create(
            model=config.AZURE_CHAT_DEPLOYMENT,
            messages=[{
                "role": "user",
                "content": REWRITE_PROMPT.format(
                    history=history_text, question=question,
                ),
            }],
            temperature=0.0,
            max_tokens=250,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        result = json.loads(raw)
        return {
            "rewritten":   result.get("rewritten", question),
            "is_followup": bool(result.get("is_followup", False)),
            "used_memory": True,
        }
    except Exception:
        return {"rewritten": question, "is_followup": False, "used_memory": False}


class RAGRetriever:
    def __init__(self):
        self.store    = get_store()
        self.store.load()
        self.embedder = load_embedder()

    def retrieve(self, question: str, mode: str = None,
                 top_k: int = config.TOP_K,
                 filter_tag: str = None) -> list[dict]:
        search_mode = mode or config.RETRIEVAL_MODE
        q_vec = self.embedder.embed_one(question)
        if search_mode == "vector":
            return self.store.vector_search(q_vec, top_k=top_k, filter_tag=filter_tag)
        elif search_mode == "fulltext":
            return self.store.fulltext_search(question, top_k=top_k)
        elif search_mode == "hybrid":
            return self.store.hybrid_search(q_vec, question, top_k=top_k)
        else:
            raise ValueError(f"Unknown mode: {search_mode}")

    def ask(self, question: str, mode: str = None,
            top_k: int = config.TOP_K,
            filter_tag: str = None,
            verbose: bool = True) -> dict:
        chunks = self.retrieve(question, mode=mode, top_k=top_k, filter_tag=filter_tag)
        if verbose:
            print(f"\n{'═'*60}")
            print(f"  {question}")
            print(f"─── {len(chunks)} chunks retrieved "
                  f"[{config.MODE} | {mode or config.RETRIEVAL_MODE}] ───")
            for i, c in enumerate(chunks):
                score = (c.get("_score_rrf") or
                         c.get("_score_vector") or
                         c.get("_score_fulltext") or 0)
                print(f"  [{i+1}] {c['source'][:35]} | "
                      f"{str(c.get('section',''))[:30]} | "
                      f"p{c.get('page','?')} | score={score:.4f}")
            print("─" * 60)
        answer = _azure_answer(question, chunks) if config.MODE == "azure" \
                 else _extractive_answer(question, chunks)
        if verbose:
            print(answer)
            print("═" * 60)
        return {"question": question, "chunks": chunks,
                "answer": answer, "mode": mode or config.RETRIEVAL_MODE}
