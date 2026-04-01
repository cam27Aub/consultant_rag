#!/usr/bin/env python3
"""Consultant RAG — Naive RAG ingestion pipeline."""
import sys
import time
import argparse
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from pipeline.cracker  import DocumentCracker
from pipeline.chunker  import chunk_all
from pipeline.enricher import ChunkEnricher
from pipeline.embedder import embed_chunks, save_embedder
from store.vector_store import get_store


def run_ingestion(docs_dir: str, strategy: str = None, use_vision: bool = True):
    start = time.time()

    print("═" * 60)
    print("  CONSULTANT RAG — INGESTION PIPELINE")
    print(f"  Mode:     {config.MODE.upper()}")
    print(f"  Strategy: {strategy or config.CHUNK_STRATEGY}")
    print(f"  Vision:   {'ON' if use_vision else 'OFF'}")
    print(f"  Files:    {', '.join(sorted(config.SUPPORTED_EXTENSIONS))}")
    print("═" * 60)

    docs_path = Path(docs_dir)
    if not docs_path.exists():
        print(f"Directory not found: {docs_dir}")
        sys.exit(1)

    files = [f for f in docs_path.iterdir()
             if f.suffix.lower() in config.SUPPORTED_EXTENSIONS]
    if not files:
        print(f"No supported documents found in {docs_dir}")
        sys.exit(1)

    print(f"\nFound {len(files)} document(s):")
    for f in files:
        size_kb = f.stat().st_size // 1024
        print(f"   • {f.name}  ({f.suffix.upper()}, {size_kb}KB)")

    print("\n" + "-" * 60)
    print("PHASE 1 — Document Cracking")
    print("-" * 60)
    cracker = DocumentCracker()
    all_units = []
    for filepath in files:
        units = cracker.crack(filepath)
        all_units.extend(units)
    print(f"\n  Total units extracted: {len(all_units)}")

    # ── PHASE 1.5 — Vision Processing ──
    vision = None
    if use_vision:
        try:
            from pipeline.vision_processor import VisionProcessor
            vision = VisionProcessor()
            print("\n" + "-" * 60)
            print("PHASE 1.5 — Vision Processing (GPT-4o)")
            print("-" * 60)

            vision_hits = 0
            file_map = {f.name: f for f in files}
            for unit in all_units:
                filepath = file_map.get(unit.source)
                if not filepath or filepath.suffix.lower() not in {".pdf", ".pptx", ".docx"}:
                    continue
                description = vision.describe_page(filepath, unit.page)
                if description:
                    vision_hits += 1
                    unit.text += "\n\n[VISUAL CONTENT ON THIS PAGE]\n" + description
                    print(f"    {unit.source} p{unit.page} — visual content extracted")

            print(f"\n  {vision_hits} pages with visual content enriched out of {len(all_units)} units")
        except ImportError as e:
            print(f"\n  Vision skipped (pymupdf not installed): {e}")
            print("  Install with: pip install pymupdf")

    print("\n" + "-" * 60)
    print(f"PHASE 2 — Chunking  [{strategy or config.CHUNK_STRATEGY}]")
    print("-" * 60)
    chunks = chunk_all(all_units, strategy=strategy)
    print(f"\n  Total chunks: {len(chunks)}")
    per_source = Counter(c.source for c in chunks)
    for source, count in per_source.items():
        avg_w = sum(len(c.chunk_text.split()) for c in chunks if c.source == source) // max(count, 1)
        print(f"     {source:45s}  {count:3d} chunks  (~{avg_w} words/chunk)")

    print("\n" + "-" * 60)
    print("PHASE 3 — Chunk Enrichment")
    print("-" * 60)
    enricher = ChunkEnricher()
    file_mtimes = {f.name: f.stat().st_mtime for f in files}
    for chunk in chunks:
        enricher.enrich(chunk, doc_mtime=file_mtimes.get(chunk.source))

    sample = chunks[0]
    print(f"\n  Sample chunk:")
    print(f"    Source:      {sample.source}")
    print(f"    Section:     {sample.section}")
    print(f"    Keywords:    {', '.join(sample.keywords[:5])}")
    print(f"    Project tag: {sample.metadata.get('project_tag')}")
    print(f"    Summary:     {sample.summary[:90]}...")
    print(f"\n  {len(chunks)} chunks enriched")

    print("\n" + "-" * 60)
    print(f"PHASE 4 — Embedding  [{config.MODE.upper()}]")
    print("-" * 60)
    chunks = embed_chunks(chunks)
    embed_dim = len(chunks[0].embedding) if chunks else 0
    print(f"  {len(chunks)} embeddings, dim={embed_dim}")

    # Save local embedder if in local mode
    save_embedder()

    print("\n" + "-" * 60)
    print(f"PHASE 5 — Indexing  [{config.MODE.upper()}]")
    print("-" * 60)
    store = get_store()

    if config.MODE == "azure":
        store.create_index()

    store.save(chunks)

    stats = store.stats()
    print(f"\n  Index stats:")
    print(f"    Total chunks:  {stats['total_chunks']}")
    print(f"    Embedding dim: {stats['embed_dim']}")

    elapsed = time.time() - start
    print(f"\n{'═'*60}")
    print(f"  Ingestion complete in {elapsed:.1f}s")
    if config.MODE == "azure":
        print(f"  Index: {config.AZURE_SEARCH_ENDPOINT}/indexes/{config.AZURE_SEARCH_INDEX}")
    print(f"  Next step → python naive_rag/query.py")
    print("═" * 60)

    return chunks


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs",      default=config.DOCS_DIR)
    parser.add_argument("--strategy",  default=None,
                        choices=["fixed", "sentence", "semantic"])
    parser.add_argument("--no-vision", action="store_true",
                        help="Skip GPT-4o Vision processing")
    args = parser.parse_args()
    run_ingestion(args.docs, strategy=args.strategy,
                  use_vision=not args.no_vision)
