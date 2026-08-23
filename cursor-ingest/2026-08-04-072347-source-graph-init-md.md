# source / graph-init.md

#doc #md

> path: source/graph-init.md  
> ext: .md  

---

# graph/__init__

#code #module #graph #code

> source_path: graph/__init__.py  
> package: graph  
> module: graph/__init__  
> hub: CODE  
> created_ts:   

---

**Package:** `graph`  
**Module:** `graph/__init__`  
**Source:** `graph/__init__.py`

graph — autonomous Obsidian vault maintenance worker.

Four operations keep the graph alive:

  clean      detect orphan nodes and dead wikilinks
  link       auto-link semantically related nodes via PSSPPS scoring
  nest       suggest hub assignments for un-tagged nodes
  commit     write an agent session (prompt + thinking + outcome) as a node

The Obsidian vault IS the hub.  Sessions are nodes.  The harmonic index is
the memory.  GitHub is not involved.

## Internal imports

`graph.worker`, `graph.logger`

---

## Semantic links

→ [[graph]]
→ [[graph]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]

## Related notes

→ [[source/mcp-server-tools-graph]]
→ [[source/graph-worker]]
→ [[source/graph-logger]]
→ [[source/graph-linker]]
→ [[source/graph-node]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[graph-logger]]
→ [[graph-worker]]
→ [[graph-index]]
→ [[mcp-server-tools-graph]]
→ [[graph-node]]
→ [[graph-linker]]

---

## Semantic links

→ [[graph-init]]
→ [[graph-worker]]
→ [[graph]]
→ [[mcp-server-tools-graph]]
→ [[graph-node]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-graph-init-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-md]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-worker-md]]
→ [[cursor-ingest/2026-08-04-072347-source-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
