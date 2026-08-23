# source / graph-node.md

#doc #md

> path: source/graph-node.md  
> ext: .md  

---

# graph/node

#code #module #graph #code

> source_path: graph/node.py  
> package: graph  
> module: graph/node  
> hub: CODE  
> created_ts:   

---

**Package:** `graph`  
**Module:** `graph/node`  
**Source:** `graph/node.py`

VaultNode — read, parse, and write Obsidian markdown nodes.

The vault root is the Spotify-rip/ subdirectory.  All paths returned are
relative to it so they match Obsidian's wikilink resolution.

## API

- `class VaultNode`
- `def _strip_code` — Remove fenced code blocks and inline code spans so wikilink
- `def load_node`
- `def load_vault` — Load every .md file in the vault, skipping .obsidian.
- `def write_session_node` — Write a session node to Spotify-rip/sessions/<timestamp>-<slug>.md.

---

## Semantic links

→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[graph]]
→ [[graph]]
→ [[obsidian-exporter]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]

## Related notes

→ [[source/graph-logger]]
→ [[source/mcp-server-tools-graph]]
→ [[source/graph-init]]
→ [[source/graph-linker]]
→ [[source/graph-ingestion]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[graph-logger]]
→ [[graph-init]]
→ [[graph-index]]
→ [[mcp-server-tools-graph]]
→ [[graph-linker]]
→ [[graph-worker]]

---

## Semantic links

→ [[graph-node]]
→ [[graph-logger]]
→ [[mcp-server-tools-graph]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[graph-ingestion]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-graph-node-py]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-logger-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-obsidian-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-md]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-graph-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
