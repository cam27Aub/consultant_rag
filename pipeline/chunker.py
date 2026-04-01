import re
from dataclasses import dataclass, field
from pipeline.cracker import PageUnit
import config


@dataclass
class ChunkUnit:
    chunk_text:   str
    chunk_index:  int
    source:       str
    doc_type:     str
    page:         int
    section:      str

    cleaned_text: str = ""
    summary:      str = ""
    keywords:     list = field(default_factory=list)
    metadata:     dict = field(default_factory=dict)

    embedding:    list = field(default_factory=list)

    def chunk_id(self) -> str:
        import hashlib
        raw = f"{self.source}-p{self.page}-c{self.chunk_index}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = {
            "id":           self.chunk_id(),
            "chunk_text":   self.chunk_text,
            "cleaned_text": self.cleaned_text,
            "summary":      self.summary,
            "keywords":     self.keywords,
            "source":       self.source,
            "doc_type":     self.doc_type,
            "page":         self.page,
            "section":      self.section,
            "metadata":     self.metadata,
            "embedding":    self.embedding,
        }
        return d


class FixedChunker:
    """
    Splits text into fixed word-count windows with configurable overlap.
    Best for: uniform documents, when structure doesn't matter.
    """
    def __init__(self, chunk_words: int = config.CHUNK_SIZE,
                 overlap_words: int = config.CHUNK_OVERLAP):
        self.chunk_words  = chunk_words
        self.overlap_words = overlap_words

    def chunk(self, unit: PageUnit) -> list[ChunkUnit]:
        words = unit.text.split()
        if len(words) < config.MIN_CHUNK_WORDS:
            return []

        chunks = []
        start = 0
        idx = 0
        while start < len(words):
            end = min(start + self.chunk_words, len(words))
            chunk_text = " ".join(words[start:end])
            chunks.append(ChunkUnit(
                chunk_text=chunk_text,
                chunk_index=idx,
                source=unit.source,
                doc_type=unit.doc_type,
                page=unit.page,
                section=unit.section,
            ))
            idx += 1
            start += self.chunk_words - self.overlap_words
            if end == len(words):
                break

        return chunks


class SentenceChunker:
    """
    Splits text into sentences, then groups sentences into chunks
    that stay below the word limit. Preserves sentence boundaries.
    Best for: narrative text, reports, methodology docs.
    """
    SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')

    def __init__(self, chunk_words: int = config.CHUNK_SIZE,
                 overlap_sentences: int = 1):
        self.chunk_words       = chunk_words
        self.overlap_sentences = overlap_sentences

    def _split_sentences(self, text: str) -> list[str]:
        raw = self.SENTENCE_RE.split(text)
        sentences = []
        for s in raw:
            for line in s.split("\n"):
                line = line.strip()
                if len(line.split()) >= 3:
                    sentences.append(line)
        return sentences

    def chunk(self, unit: PageUnit) -> list[ChunkUnit]:
        sentences = self._split_sentences(unit.text)
        if not sentences:
            return []

        chunks = []
        current = []
        current_words = 0
        idx = 0

        for sent in sentences:
            sent_words = len(sent.split())
            if current_words + sent_words > self.chunk_words and current:
                chunk_text = " ".join(current)
                if len(chunk_text.split()) >= config.MIN_CHUNK_WORDS:
                    chunks.append(ChunkUnit(
                        chunk_text=chunk_text,
                        chunk_index=idx,
                        source=unit.source,
                        doc_type=unit.doc_type,
                        page=unit.page,
                        section=unit.section,
                    ))
                    idx += 1
                current = current[-self.overlap_sentences:] if self.overlap_sentences else []
                current_words = sum(len(s.split()) for s in current)

            current.append(sent)
            current_words += sent_words

        if current:
            chunk_text = " ".join(current)
            if len(chunk_text.split()) >= config.MIN_CHUNK_WORDS:
                chunks.append(ChunkUnit(
                    chunk_text=chunk_text,
                    chunk_index=idx,
                    source=unit.source,
                    doc_type=unit.doc_type,
                    page=unit.page,
                    section=unit.section,
                ))

        return chunks


class SemanticChunker:
    """
    Groups paragraphs together as long as they are 'related'.
    Relationship is measured by word overlap (Jaccard similarity).
    New chunk starts when similarity to the current chunk drops.

    Best for: structured documents with clear section breaks,
    policy docs, Excel sheets with labeled sections.
    """
    def __init__(self, chunk_words: int = config.CHUNK_SIZE,
                 sim_threshold: float = 0.15):
        self.chunk_words   = chunk_words
        self.sim_threshold = sim_threshold

    def _jaccard(self, a: str, b: str) -> float:
        sa = set(a.lower().split())
        sb = set(b.lower().split())
        stops = {"the","a","an","is","are","was","were","and","or","of",
                 "to","in","for","on","with","at","by","from","as","that"}
        sa -= stops
        sb -= stops
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)

    def chunk(self, unit: PageUnit) -> list[ChunkUnit]:
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n|\n(?=[A-Z\d])', unit.text) if p.strip()]
        if not paragraphs:
            return []

        chunks = []
        current = []
        current_words = 0
        idx = 0

        for para in paragraphs:
            para_words = len(para.split())

            if current:
                current_text = " ".join(current)
                sim = self._jaccard(current_text[-200:], para)
                force_new = (
                    current_words + para_words > self.chunk_words or
                    sim < self.sim_threshold
                )
            else:
                force_new = False

            if force_new and current:
                chunk_text = "\n".join(current)
                if len(chunk_text.split()) >= config.MIN_CHUNK_WORDS:
                    chunks.append(ChunkUnit(
                        chunk_text=chunk_text,
                        chunk_index=idx,
                        source=unit.source,
                        doc_type=unit.doc_type,
                        page=unit.page,
                        section=unit.section,
                    ))
                    idx += 1
                current = []
                current_words = 0

            current.append(para)
            current_words += para_words

        if current:
            chunk_text = "\n".join(current)
            if len(chunk_text.split()) >= config.MIN_CHUNK_WORDS:
                chunks.append(ChunkUnit(
                    chunk_text=chunk_text,
                    chunk_index=idx,
                    source=unit.source,
                    doc_type=unit.doc_type,
                    page=unit.page,
                    section=unit.section,
                ))

        return chunks


def get_chunker(strategy: str = None):
    s = strategy or config.CHUNK_STRATEGY
    if s == "fixed":
        return FixedChunker()
    elif s == "sentence":
        return SentenceChunker()
    elif s == "semantic":
        return SemanticChunker()
    else:
        raise ValueError(f"Unknown chunking strategy: {s}. Use: fixed | sentence | semantic")


def chunk_all(units: list[PageUnit], strategy: str = None) -> list[ChunkUnit]:
    """Chunk a list of PageUnits using the selected strategy."""
    chunker = get_chunker(strategy)
    all_chunks = []
    for unit in units:
        chunks = chunker.chunk(unit)
        all_chunks.extend(chunks)
    return all_chunks
