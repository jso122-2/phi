# source / mcp-server-tools-temporal.md

#doc #md

> path: source/mcp-server-tools-temporal.md  
> ext: .md  

---

# mcp_server/tools/temporal

#code #module #mcp-server #code

> source_path: mcp_server/tools/temporal.py  
> package: mcp_server  
> module: mcp_server/tools/temporal  
> hub: CODE  
> created_ts:   

---

**Package:** `mcp_server`  
**Module:** `mcp_server/tools/temporal`  
**Source:** `mcp_server/tools/temporal.py`

Temporal sharding index tools: state, vector, coherence, record, advance, reset.

## API

- `def temporal_state` — Return the full state of the temporal sharding index.
- `def temporal_vector` — Return the (n_hubs × n_windows) temporal activation matrix.
- `def temporal_coherence` — Return the Ana-Chi coherence of the temporal index.
- `def temporal_record` — Record activation for a CAIRRN hub in the temporal index at t=0 (now).
- `def temporal_advance` — Advance the temporal index by `steps` clock ticks.
- `def temporal_reset` — Reset the temporal index — zero all activations and reset clock to 0.

## Internal imports

`mcp_server._gate`, `mcp_server._state`, `sims.temporal`

---

## Semantic links

→ [[temporal-index]]
→ [[temporal-index]]
→ [[harmonic-index]]
→ [[harmonic-index]]
→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]

## Related notes

→ [[source/mcp-server-tools-harmonic]]
→ [[source/mcp-server-tools-cairrn]]
→ [[source/mcp-server-tools-forecast]]
→ [[source/sims-temporal]]
→ [[source/engine-cursor-tracer]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[mcp-server-main]]
→ [[mcp-index]]
→ [[mcp-server-tools-harmonic]]
→ [[mcp-server-tools-forecast]]
→ [[mcp-server-tools-init]]
→ [[mcp-server-tools-cairrn]]

---

## Semantic links

→ [[mcp-server-tools-temporal]]
→ [[mcp-server-server]]
→ [[mcp-server-main]]
→ [[mcp-server-tools-modular]]
→ [[mcp-server-tools-system]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-state-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-modular-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
