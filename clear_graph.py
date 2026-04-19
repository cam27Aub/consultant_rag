"""One-shot script to wipe all vertices from Cosmos DB Gremlin graph in batches."""
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from graph_rag.graph_store import GraphStore
import time

s = GraphStore()
print("Dropping all vertices in batches of 100...")

total_dropped = 0
while True:
    # Get a batch of vertex IDs
    ids = s._run("g.V().limit(100).id().fold()")
    batch = ids[0] if ids else []
    if not batch:
        break
    # Drop them one by one using their IDs
    for vid in batch:
        s._run(f"g.V('{vid}').drop()")
    total_dropped += len(batch)
    print(f"  Dropped {total_dropped} vertices so far...")
    time.sleep(0.5)

stats = s.stats()
print(f"Done. Graph now has {stats['vertices']} nodes, {stats['edges']} edges.")
s.close()
