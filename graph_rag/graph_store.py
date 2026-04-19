"""
graph_store.py — Manages the knowledge graph in Azure Cosmos DB (Gremlin API).

Confirmed Cosmos DB valueMap(true) format:
  id, label -> plain strings
  name, description, source, page -> lists (take index 0)
"""
from gremlin_python.driver import client, serializer
from graph_rag import config_graph as config


def _first(v):
    """Unwrap Cosmos DB list-wrapped property values."""
    if isinstance(v, list):
        return v[0] if v else ""
    return v


class GraphStore:
    def __init__(self):
        self.client = client.Client(
            url=config.GREMLIN_ENDPOINT,
            traversal_source="g",
            username=f"/dbs/{config.GREMLIN_DATABASE}/colls/{config.GREMLIN_GRAPH}",
            password=config.GREMLIN_KEY,
            message_serializer=serializer.GraphSONSerializersV2d0(),
        )
        self._vertex_cache = None  # cached vertices for fast search
        print("  Connected to Azure Cosmos DB (Gremlin)")

    def _connect(self):
        self.client = client.Client(
            url=config.GREMLIN_ENDPOINT,
            traversal_source="g",
            username="/dbs/%s/colls/%s" % (config.GREMLIN_DATABASE, config.GREMLIN_GRAPH),
            password=config.GREMLIN_KEY,
            message_serializer=serializer.GraphSONSerializersV2d0(),
        )

    def _run(self, query, retries=2, timeout=45):
        for attempt in range(retries + 1):
            try:
                callback = self.client.submitAsync(query)
                return callback.result().all().result(timeout=timeout)
            except RuntimeError as e:
                if "closed" in str(e).lower() and attempt < retries:
                    print("  Reconnecting to Cosmos DB...")
                    self._connect()
                else:
                    raise

    def upsert_entity(self, entity):
        eid   = entity["id"].replace("'", "\\'")
        label = entity.get("label", "Concept").replace("'", "\\'")
        name  = entity.get("name", eid).replace("'", "\\'")
        desc  = entity.get("description", "").replace("'", "\\'")[:300]
        src   = entity.get("source", "").replace("'", "\\'")
        page  = int(entity.get("page", 0))
        try:
            self._run("g.V('%s').drop()" % eid)
        except Exception:
            pass
        self._run(
            "g.addV('%s')"
            ".property('id','%s')"
            ".property('pk','%s')"
            ".property('name','%s')"
            ".property('description','%s')"
            ".property('source','%s')"
            ".property('page',%d)"
            % (label, eid, eid, name, desc, src, page)
        )

    def upsert_relationship(self, from_id, to_id, rel_type):
        from_id  = from_id.replace("'", "\\'")
        to_id    = to_id.replace("'", "\\'")
        rel_type = rel_type.replace("'", "\\'")
        try:
            self._run(
                "g.V('%s').addE('%s').to(g.V('%s'))"
                % (from_id, rel_type, to_id)
            )
        except Exception as e:
            print("  Edge %s -[%s]-> %s failed: %s" % (from_id, rel_type, to_id, e))

    def delete_by_source(self, source):
        source = source.replace("'", "\\'")
        try:
            self._run("g.V().has('source','%s').drop()" % source)
            print("  Dropped nodes for '%s'" % source)
        except Exception:
            print("  No existing nodes for '%s'" % source)

    def clear_cache(self):
        """Clear the vertex cache (call after ingesting new documents)."""
        self._vertex_cache = None

    def search_entities(self, query_terms, top_k=5):
        """
        Fetch all vertices and score them against query terms in Python.
        Cosmos DB does not support the containing() Gremlin predicate.
        Uses in-memory cache to avoid re-fetching on every query.

        Scoring priorities:
        - Full multi-word phrase match in name  → highest (10)
        - Full phrase match in description      → good (3)
        - ALL words of a multi-word term found  → good (6 name / 2 desc)
        - Single-word match alone               → low (1 name / 0.5 desc)
        This prevents "Buyer Behavior" from strongly matching entities
        that only contain "Behavior" without "Buyer".
        """
        try:
            if self._vertex_cache is None:
                self._vertex_cache = self._run("g.V().valueMap(true).limit(500)", timeout=60)
            all_vertices = self._vertex_cache
        except Exception:
            return []

        scored = []
        for r in all_vertices:
            name = str(_first(r.get("name", ""))).lower()
            desc = str(_first(r.get("description", ""))).lower()
            score = 0
            for term in query_terms:
                t = term.lower()
                words = [w for w in t.split() if len(w) > 2]

                # Full phrase match — strongest signal
                if t in name:
                    score += 10
                elif t in desc:
                    score += 3
                elif len(words) > 1:
                    # Multi-word term: check how many words match
                    name_hits = sum(1 for w in words if w in name)
                    desc_hits = sum(1 for w in words if w in desc)
                    if name_hits == len(words):
                        # All words present in name — strong match
                        score += 6
                    elif name_hits > 0:
                        # Partial word match in name — weak, scaled down
                        score += name_hits * 0.5
                    if desc_hits == len(words):
                        score += 2
                    elif desc_hits > 0 and name_hits == 0:
                        score += desc_hits * 0.3
                else:
                    # Single-word term
                    if len(t) > 3:
                        if t in name:
                            score += 3
                        elif t in desc:
                            score += 1
            if score > 0:
                scored.append((score, r))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        seen = set()
        for match_score, r in scored[:top_k]:
            eid = str(r.get("id", ""))
            if eid not in seen:
                seen.add(eid)
                v = self._parse_vertex(r)
                v["_match_score"] = match_score
                results.append(v)
        return results

    def get_neighbours(self, entity_id, depth=2):
        eid = entity_id.replace("'", "\\'")
        nodes, edges = [], []
        seen_v, seen_e = set(), set()

        try:
            seed = self._run("g.V('%s').valueMap(true)" % eid)
            for r in seed:
                nodes.append(self._parse_vertex(r))
                seen_v.add(eid)
        except Exception:
            return {"nodes": [], "edges": []}

        frontier = [eid]
        for _ in range(depth):
            next_frontier = []
            for vid in frontier:
                vid = vid.replace("'", "\\'")
                try:
                    out_edges = self._run(
                        "g.V('%s').outE().limit(20)"
                        ".project('from','label','to')"
                        ".by(__.outV().id())"
                        ".by(__.label())"
                        ".by(__.inV().id())"
                        % vid
                    )
                    for e in out_edges:
                        ekey = "%s-%s-%s" % (e.get("from"), e.get("label"), e.get("to"))
                        if ekey not in seen_e:
                            seen_e.add(ekey)
                            edges.append({
                                "from": str(e.get("from", "")),
                                "to":   str(e.get("to",   "")),
                                "type": str(e.get("label",""))
                            })
                            to_id = str(e.get("to", ""))
                            if to_id not in seen_v:
                                seen_v.add(to_id)
                                next_frontier.append(to_id)
                                nb = self._run("g.V('%s').valueMap(true)" % to_id)
                                for r in nb:
                                    nodes.append(self._parse_vertex(r))
                except Exception:
                    pass
            frontier = next_frontier
            if not frontier:
                break

        return {"nodes": nodes, "edges": edges}

    def stats(self):
        try:
            v = self._run("g.V().count()")[0]
            e = self._run("g.E().count()")[0]
        except Exception:
            v, e = 0, 0
        return {"vertices": v, "edges": e}

    @staticmethod
    def _parse_vertex(r):
        return {
            "id":          str(r.get("id",          "")),
            "label":       str(r.get("label",        "Concept")),
            "name":        str(_first(r.get("name",        ""))),
            "description": str(_first(r.get("description", ""))),
            "source":      str(_first(r.get("source",      ""))),
            "page":        _first(r.get("page", 0)),
        }

    def close(self):
        self.client.close()
