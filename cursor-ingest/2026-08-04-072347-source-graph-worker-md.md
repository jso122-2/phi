# source / graph-worker.md

#doc #md

> path: source/graph-worker.md  
> ext: .md  

---

# graph/worker

#code #module #graph #code

> source_path: graph/worker.py  
> package: graph  
> module: graph/worker  
> hub: CODE  
> created_ts:   

---

**Package:** `graph`  
**Module:** `graph/worker`  
**Source:** `graph/worker.py`

GraphWorker — autonomous Obsidian graph maintenance.

Four operations:

  run_clean      find orphan nodes + dead wikilinks
  run_link       auto-link semantically related nodes (calls linker.link_all)
  run_nest       suggest hub assignments for untagged nodes
  run_status     full graph health snapshot

## API

- `def _resolve_link` — Resolve a wikilink to its canonical bare stem, stripping any path prefix.
- `class CleanReport`
- `class LinkReport`
- `class NestReport`
- `class GraphStatus`
- `def run_clean` — Scan the vault for structural problems:
- `def run_link` — Auto-link semantically related nodes. Writes changes to disk.
- `def run_nest` — Suggest hub assignment for nodes that have no hub-level tags.
- `def run_status` — Full graph health snapshot — runs clean + counts, no file writes.

## Internal imports

`graph.node`, `graph.linker`

---

## Semantic links

→ [[graph]]
→ [[graph]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[logger]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]

## Related notes

→ [[source/graph-init]]
→ [[source/mcp-server-tools-graph]]
→ [[source/graph-linker]]
→ [[source/tools-fix-dead-links]]
→ [[source/graph-node]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[graph-init]]
→ [[graph-logger]]
→ [[mcp-server-tools-graph]]
→ [[graph-index]]
→ [[graph-node]]
→ [[graph-linker]]

---

## Semantic links

→ [[graph-worker]]
→ [[graph-init]]
→ [[graph]]
→ [[graph]]
→ [[graph-linker]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-graph-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-init-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-linker-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
