# source / mcp-server-tools-graph.md

#doc #md

> path: source/mcp-server-tools-graph.md  
> ext: .md  

---

# mcp_server/tools/graph

#code #module #mcp-server #code

> source_path: mcp_server/tools/graph.py  
> package: mcp_server  
> module: mcp_server/tools/graph  
> hub: CODE  
> created_ts:   

---

**Package:** `mcp_server`  
**Module:** `mcp_server/tools/graph`  
**Source:** `mcp_server/tools/graph.py`

Graph / vault tools: commit, clean, nest, link, sync, ingest, status, traverse, hub.

## API

- `def graph_commit` — Commit this agent session to the Obsidian vault as a permanent node.
- `def graph_clean` — Scan the Obsidian vault for structural problems (orphans + dead wikilinks).
- `def graph_nest` — Suggest semantic hub assignments for untagged vault nodes.
- `def graph_link` — Auto-link semantically related nodes across the vault (TF-IDF cosine > threshold).
- `def graph_sync_manifest` — Apply an ingestion manifest to the harmonic index.
- `def graph_ingest` — Run the Oesophagus ingestion pipeline against a source directory.
- `def graph_status` — Full graph health snapshot — node counts, sessions, orphans, dead links,
- `def graph_traverse` — Ride the semantic minecart through the Obsidian vault graph.
- `def graph_ingest_source` — Ingest Python source modules from this project into the Obsidian vault graph.
- `def vault_hub_state` — Return the current state of the Vault Hub backwards channel.

## Internal imports

`mcp_server._gate`, `mcp_server._state`, `graph.logger`, `graph.node`, `graph.worker`, `psspps.scorer`, `sims.harmonic`, `sims.temporal`, `workers.oesophagus`, `psspps.embedder`, `psspps.retriever`, `psspps.traverser`

---

## Semantic links

→ [[graph]]
→ [[graph]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]

## Related notes

→ [[source/graph-init]]
→ [[source/graph-node]]
→ [[source/graph-logger]]
→ [[source/graph-ingestion]]
→ [[source/graph-worker]]

— import index  

*Imported by `graph/in

---

## Semantic links

→ [[mcp-server-tools-graph]]
→ [[mcp-server-main]]
→ [[mcp-server-server]]
→ [[scripts-samba-mcp-server]]
→ [[mcp-index]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-modular-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-temporal-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
