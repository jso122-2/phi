# source / mcp-server-tools-harmonic.md

#doc #md

> path: source/mcp-server-tools-harmonic.md  
> ext: .md  

---

# mcp_server/tools/harmonic

#code #module #mcp-server #code

> source_path: mcp_server/tools/harmonic.py  
> package: mcp_server  
> module: mcp_server/tools/harmonic  
> hub: CODE  
> created_ts:   

---

**Package:** `mcp_server`  
**Module:** `mcp_server/tools/harmonic`  
**Source:** `mcp_server/tools/harmonic.py`

Harmonic index tools: state, propagate, inject, hub ops, reset, goal.

## API

- `def harmonic_index_state` — Return the current state of the harmonically-sharded propagation index.
- `def harmonic_propagate` — Advance the harmonic index by `steps` propagation cycles.
- `def harmonic_inject` — Directly inject activation into a specific shard of the harmonic index.
- `def hub_inject` — Inject activation into the harmonic index via a station-hub name.
- `def hub_state` — Return the harmonic index state broken down by station hub.
- `def harmonic_set_goal` — Set the goal for goal-directed propagation.
- `def harmonic_clear_goal` — Clear the current goal from the harmonic index.
- `def harmonic_reset` — Reset the harmonic index — zero all activations and step counter.

## Internal imports

`mcp_server._gate`, `mcp_server._state`, `sims.harmonic`

---

## Semantic links

→ [[harmonic-index]]
→ [[harmonic-index]]
→ [[live-state]]
→ [[attractors]]
→ [[sims]]

## Related notes

→ [[source/sims-harmonic]]
→ [[source/mcp-server-tools-temporal]]
→ [[source/mcp-server-tools-forecast]]
→ [[source/sims-temporal]]
→ [[source/engine-bridge-factory]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[mcp-server-main]]
→ [[mcp-server-tools-temporal]]
→ [[mcp-server-tools-forecast]]
→ [[mcp-index]]
→ [[mcp-server-server]]
→ [[mcp-server-tools-init]]

---

## Semantic links

→ [[mcp-server-tools-harmonic]]
→ [[mcp-server-server]]
→ [[mcp-server-main]]
→ [[mcp-server-tools-system]]
→ [[mcp-index]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-harmonic-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-modular-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
