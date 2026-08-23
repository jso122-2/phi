# source / graph-logger.md

#doc #md

> path: source/graph-logger.md  
> ext: .md  

---

# graph/logger

#code #module #graph #code

> source_path: graph/logger.py  
> package: graph  
> module: graph/logger  
> hub: CODE  
> created_ts:   

---

**Package:** `graph`  
**Module:** `graph/logger`  
**Source:** `graph/logger.py`

PromptLogger — write every agent session to the Obsidian vault as a node.

The vault IS the hub.  Every prompt + thinking + outcome becomes a permanent
node in Spotify-rip/sessions/.  PSSPPS discovers which existing nodes are
most semantically related and injects those as wikilinks.

This is the "push to graph" operation — it replaces git push for this project.

## API

- `def log_session` — Write this session to the vault and discover related graph links.

## Internal imports

`graph.node`, `psspps.pipeline`

---

## Semantic links

→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[graph]]
→ [[graph]]
→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]

## Related notes

→ [[source/graph-node]]
→ [[source/graph-init]]
→ [[source/mcp-server-tools-graph]]
→ [[source/graph-linker]]
→ [[source/graph-ingestion]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[graph-init]]
→ [[graph-node]]
→ [[graph-index]]
→ [[mcp-server-tools-graph]]
→ [[graph-worker]]
→ [[graph-linker]]

---

## Semantic links

→ [[graph-logger]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[graph-node]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-graph-logger-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-node-md]]
→ [[cursor-ingest/2026-08-04-072347-graph-node-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-md]]
→ [[cursor-ingest/2026-08-04-072347-readme-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
