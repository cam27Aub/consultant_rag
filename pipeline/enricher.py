import re
import math
import string
from pathlib import Path
from datetime import datetime
from collections import Counter
from pipeline.chunker import ChunkUnit


class ChunkCleaner:
    """
    Applies normalisation rules to eliminate noise that doesn't
    affect semantic meaning. Supports closeness matching.
    """

    BOILERPLATE = [
        r"CONFIDENTIAL\s*[-–—]*\s*INTERNAL USE ONLY",
        r"Page\s+\d+\s+of\s+\d+",
        r"©\s*\d{4}.*?(All rights reserved\.?)?",
        r"\bDraft\b",
        r"Strictly Confidential",
    ]

    def clean(self, text: str) -> str:
        text = text.replace("\u2019", "'").replace("\u2018", "'")
        text = text.replace("\u201c", '"').replace("\u201d", '"')
        text = text.replace("\u2013", "-").replace("\u2014", "-")
        text = text.replace("\u00a0", " ")

        for pattern in self.BOILERPLATE:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\n[ \t]+", "\n", text)

        text = re.sub(r"^\s*[-=_*•·]{3,}\s*$", "", text, flags=re.MULTILINE)

        return text.strip()


STOPWORDS = {
    "the","a","an","is","are","was","were","be","been","being",
    "have","has","had","do","does","did","will","would","shall","should",
    "may","might","must","can","could","and","or","but","if","then",
    "that","this","these","those","it","its","we","our","you","your",
    "they","their","in","on","at","to","for","of","with","by","from",
    "as","up","not","no","so","than","more","also","such","other",
    "each","which","who","what","when","where","how","all","any",
    "both","few","some","many","most","only","same","than","too",
    "very","just","into","over","after","about","above","below",
    "between","through","during","before","he","she","his","her",
    "him","i","me","my","we","us","them","there","here"
}

PROJECT_TAGS = {
    "retail":           ["retail","grocery","fashion","ebitda","store","merchandise","inventory"],
    "digital":          ["digital","transformation","cloud","api","data","analytics","platform"],
    "market entry":     ["market","entry","expansion","mena","region","saudi","uae","launch"],
    "hr & policy":      ["travel","expense","policy","hotel","flight","reimbursement","consultant"],
    "benchmarking":     ["benchmark","margin","performance","peer","comparison","kpi","metric"],
    "strategy":         ["strategy","roadmap","vision","initiative","planning","objective"],
}

def infer_project_tag(text: str, filename: str) -> str:
    combined = (text + " " + filename).lower()
    scores = {}
    for tag, keywords in PROJECT_TAGS.items():
        scores[tag] = sum(combined.count(kw) for kw in keywords)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


def extract_keywords(text: str, top_n: int = 8) -> list[str]:
    """
    Simple TF-inspired keyword extraction using word frequency
    after stopword removal. Returns top N content words.
    """
    words = re.findall(r'\b[a-zA-Z][a-zA-Z\-]{2,}\b', text.lower())
    words = [w for w in words if w not in STOPWORDS and len(w) > 3]
    freq = Counter(words)
    return [word for word, _ in freq.most_common(top_n)]


def generate_summary(text: str, max_sentences: int = 2) -> str:
    """
    Extractive summary — picks the most 'central' sentences using
    word overlap scoring (lightweight alternative to LLM summarisation).
    """
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if len(s.split()) > 6]

    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    all_words = [w for w in text.lower().split() if w not in STOPWORDS]
    freq = Counter(all_words)

    def score(sent):
        words = [w for w in sent.lower().split() if w not in STOPWORDS]
        return sum(freq.get(w, 0) for w in words) / max(len(words), 1)

    scored = sorted(enumerate(sentences), key=lambda x: score(x[1]), reverse=True)
    top_idx = sorted([i for i, _ in scored[:max_sentences]])
    return " ".join(sentences[i] for i in top_idx)


class ChunkEnricher:

    def __init__(self):
        self.cleaner = ChunkCleaner()

    def enrich(self, chunk: ChunkUnit, doc_mtime: float = None) -> ChunkUnit:
        chunk.cleaned_text = self.cleaner.clean(chunk.chunk_text)
        chunk.keywords = extract_keywords(chunk.cleaned_text)
        chunk.summary = generate_summary(chunk.cleaned_text)
        chunk.metadata = {
            "project_tag": infer_project_tag(chunk.chunk_text, chunk.source),
            "doc_date":    (
                datetime.fromtimestamp(doc_mtime).strftime("%Y-%m-%d")
                if doc_mtime else datetime.now().strftime("%Y-%m-%d")
            ),
            "word_count":  len(chunk.cleaned_text.split()),
            "has_table":   "TABLE DATA" in chunk.chunk_text,
            "char_count":  len(chunk.cleaned_text),
        }

        return chunk

    def enrich_all(self, chunks: list[ChunkUnit],
                   filepath: "Path | None" = None) -> list[ChunkUnit]:
        mtime = filepath.stat().st_mtime if filepath else None
        enriched = []
        for chunk in chunks:
            enriched.append(self.enrich(chunk, doc_mtime=mtime))
        return enriched
