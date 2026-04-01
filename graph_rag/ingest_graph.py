"""
ingest_graph.py — Ingestion pipeline for Graph RAG with GPT-4o Vision support.

For each document:
  1. Crack text (reuses existing pipeline/cracker.py)
  2. Chunk text
  3. For each chunk:
     a. GPT-4o Vision describes any charts/diagrams on the page
     b. Vision description is appended to text
     c. GPT-4o extracts entities + relationships from combined text
  4. Upsert nodes and edges into Cosmos DB (Gremlin)

Usage:
  python ingest_graph.py                    # ingest all docs in sample_docs/
  python ingest_graph.py --file report.pdf  # ingest a single file
  python ingest_graph.py --no-vision        # skip vision processing
"""
import asyncio, sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import sys
import argparse
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.cracker    import DocumentCracker
from pipeline.chunker    import SentenceChunker
from graph_rag.extractor        import EntityExtractor
from graph_rag.graph_store      import GraphStore
from pipeline.vision_processor import VisionProcessor
from graph_rag import config_graph as config


def ingest_file(path: Path, cracker, chunker, extractor, store,
                vision=None, overwrite=True):
    print(f"\nIngesting: {path.name}")

    if overwrite:
        store.delete_by_source(path.name)

    # crack
    units = cracker.crack(path)
    print(f"  {len(units)} page units extracted")

    # chunk
    chunks = []
    for u in units:
        chunks.extend(chunker.chunk(u))
    print(f"  {len(chunks)} chunks created")

    total_entities = 0
    total_rels     = 0
    vision_hits    = 0

    for i, chunk in enumerate(chunks):
        text   = getattr(chunk, "cleaned_text", None) or getattr(chunk, "chunk_text", "")
        source = getattr(chunk, "source", path.name)
        page   = getattr(chunk, "page", i + 1)

        if len(text.strip()) < 30:
            continue

        # vision: describe visual content on this page
        visual_description = ""
        if vision and path.suffix.lower() in {".pdf", ".pptx", ".docx"}:
            visual_description = vision.describe_page(path, page)
            if visual_description:
                vision_hits += 1
                print(f"  Chunk {i+1}/{len(chunks)} — vision content detected on p{page}")

        # merge text + visual description
        combined_text = text
        if visual_description:
            combined_text = (
                text
                + "\n\n[VISUAL CONTENT ON THIS PAGE]\n"
                + visual_description
            )

        print(f"  Chunk {i+1}/{len(chunks)} — extracting entities...")
        result = extractor.extract(combined_text, source, page)

        entities      = result.get("entities", [])
        relationships = result.get("relationships", [])

        for entity in entities:
            store.upsert_entity(entity)
        total_entities += len(entities)

        entity_ids = {e["id"] for e in entities}
        for rel in relationships:
            if rel["from"] in entity_ids and rel["to"] in entity_ids:
                store.upsert_relationship(rel["from"], rel["to"], rel["type"])
        total_rels += len(relationships)

        time.sleep(0.5)

    print(
        f"  {path.name} — {total_entities} entities, "
        f"{total_rels} relationships, {vision_hits} pages with visuals"
    )
    return total_entities, total_rels


def main():
    parser = argparse.ArgumentParser(description="Graph RAG Ingestion with Vision")
    parser.add_argument("--file",       type=str,  default=None,  help="Single file to ingest")
    parser.add_argument("--docs",       type=str,  default=None,  help="Docs folder")
    parser.add_argument("--no-overwrite", action="store_true",    help="Keep existing nodes")
    parser.add_argument("--no-vision",  action="store_true",      help="Skip GPT-4o Vision")
    args = parser.parse_args()

    docs_dir  = Path(args.docs) if args.docs else Path(__file__).parent.parent / "sample_docs"
    cracker   = DocumentCracker()
    chunker   = SentenceChunker(chunk_words=config.CHUNK_WORDS)
    extractor = EntityExtractor()
    store     = GraphStore()
    vision    = None if args.no_vision else VisionProcessor()
    overwrite = not args.no_overwrite

    if vision:
        print("  GPT-4o Vision enabled — visual content will be extracted")
    else:
        print("  Vision disabled — text only")

    if args.file:
        path = Path(args.file)
        if not path.exists():
            path = docs_dir / args.file
        ingest_file(path, cracker, chunker, extractor, store, vision, overwrite)
    else:
        files = [
            f for f in docs_dir.iterdir()
            if f.suffix.lower() in config.SUPPORTED_EXTENSIONS
        ]
        if not files:
            print(f"No supported files found in {docs_dir}")
            return

        print(f"Found {len(files)} documents in {docs_dir}")
        total_e, total_r = 0, 0
        for f in files:
            e, r = ingest_file(f, cracker, chunker, extractor, store, vision, overwrite)
            total_e += e
            total_r += r

        print(
            f"\nIngestion complete — {total_e} entities, "
            f"{total_r} relationships across {len(files)} documents"
        )

    stats = store.stats()
    print(f"Graph — {stats['vertices']} nodes, {stats['edges']} edges in Cosmos DB")
    store.close()


if __name__ == "__main__":
    main()
