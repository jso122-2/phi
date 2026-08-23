# source / mcp-server-tools-cairrn.md

#doc #md

> path: source/mcp-server-tools-cairrn.md  
> ext: .md  

---

# mcp_server/tools/cairrn

#code #module #mcp-server #code

> source_path: mcp_server/tools/cairrn.py  
> package: mcp_server  
> module: mcp_server/tools/cairrn  
> hub: CODE  
> created_ts:   

---

**Package:** `mcp_server`  
**Module:** `mcp_server/tools/cairrn`  
**Source:** `mcp_server/tools/cairrn.py`

CAIRRN tools: hub geometry, single-hub run, batch run.

## API

- `def cairrn_hub_state` — Report the static CAIRRN shard geometry across all five station hubs.
- `def cairrn_hub_run` — Run the full CAIRRN four-layer pipeline for a given hub and metric.
- `def cairrn_batch_run` — Run the CAIRRN four-layer pipeline across ALL five station hubs simultaneously.

## Internal imports

`mcp_server._gate`, `mcp_server._state`, `sims.temporal`, `workers.cairrn`

---

## Semantic links

→ [[2026-07-16-011935-cairrn-cairrn-worker-system]]
→ [[COMMANDS]]
→ [[2026-07-13-095004-cairrnify-the-mcp-server-fix-dom-queue-open]]
→ [[hub-classifier]]
→ [[COMMANDS]]

## Related notes

→ [[source/mcp-server-tools-temporal]]
→ [[source/mcp-server-tools-prefeed-shuffle]]
→ [[source/engine-cairrn-bridge]]
→ [[source/workers-cairrn-worker]]
→ [[source/mcp-server-tools-phi-dispatch]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[mcp-index]]
→ [[mcp-server-main]]
→ [[mcp-server-tools-init]]
→ [[mcp-server-server]]
→ [[index]]
→ [[mcp-server-tools-search]]

---

## Semantic links

→ [[mcp-server-tools-cairrn]]
→ [[mcp-server-main]]
→ [[mcp-server-server]]
→ [[mcp-index]]
→ [[mcp-server-tools-system]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-modular-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-state-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
