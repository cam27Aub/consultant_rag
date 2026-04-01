import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gremlin_python.driver import client, serializer
from graph_rag import config_graph as config

c = client.Client(
    url=config.GREMLIN_ENDPOINT,
    traversal_source="g",
    username=f"/dbs/{config.GREMLIN_DATABASE}/colls/{config.GREMLIN_GRAPH}",
    password=config.GREMLIN_KEY,
    message_serializer=serializer.GraphSONSerializersV2d0(),
)

# Check vertex count
count = c.submitAsync("g.V().count()").result().all().result()
print(f"Total vertices: {count}")

# Fetch 3 raw vertices and print exactly what comes back
print("\n--- Raw valueMap(true) output ---")
rows = c.submitAsync("g.V().limit(3).valueMap(true)").result().all().result()
for i, r in enumerate(rows):
    print(f"\nVertex {i+1}: {r}")
    print(f"  type: {type(r)}")
    for k, v in r.items():
        print(f"  key={k!r}  val={v!r}  val_type={type(v)}")

# Also try without 'true'
print("\n--- Raw valueMap() output (no true) ---")
rows2 = c.submitAsync("g.V().limit(3).valueMap()").result().all().result()
for i, r in enumerate(rows2):
    print(f"\nVertex {i+1}: {r}")

c.close()
