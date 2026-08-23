# source / mcp-server-tools-phi-dispatch.md

#doc #md

> path: source/mcp-server-tools-phi-dispatch.md  
> ext: .md  

---

# mcp_server/tools/phi_dispatch

#code #module #mcp-server #code

> source_path: mcp_server/tools/phi_dispatch.py  
> package: mcp_server  
> module: mcp_server/tools/phi_dispatch  
> hub: CODE  
> created_ts:   

---

**Package:** `mcp_server`  
**Module:** `mcp_server/tools/phi_dispatch`  
**Source:** `mcp_server/tools/phi_dispatch.py`

phi_dispatch — MCP tools for the CAIRRN-bound action dispatcher.

All phi operations (clip, shuffle, inject, propagate, CAIRRN run,
temporal record) flow through a single CAIRRNDispatcher that gates
execution by CODE hub coherence.

Four tools:

    phi_enqueue   — add any phi action to the CAIRRN queue
    phi_step      — one dispatcher clock tick (gate check + dispatch)
    phi_queue     — inspect queue + gate state
    phi_flush     — force-dispatch all queued actions immediately

The dispatcher singleton is lazy-constructed on first call.
It shares state with all existing tools:
  - _harmonic_index from _state    (HarmonicIndex — gate signal + inject)
  - _temporal_index from _state    (TemporalShardIndex — TEMPORAL_REC)
  - phi_clip._get_session()        (PhiTracerSession — CLIP, SHUFFLE_*)
  - prefeed_shuffle._get_shuffle() (CAIRRNPrefeedShuffle — SHUFFLE_*)

## API

- `def _get_dispatcher` — Lazy-construct the CAIRRNDispatcher singleton.
- `def phi_enqueue` — Enqueue a phi action in the CAIRRN dispatcher.
- `def phi_step` — One CAIRRN dispatcher clock tick.
- `def phi_queue` — Inspect the CAIRRN dispatcher queue and gate state.
- `def phi_flush` — Force-dispatch all queued actions immediately, bypassing the coherence gate.

## Internal imports

`mcp_server._gate`, `mcp_server._state`, `engine.cairrn_dispatch`, `mcp_server.tools.phi_clip`, `mcp_server.tools.prefeed_shuffle`

---

## Semantic links

→ [[COMMANDS]]
→ [[COMMANDS]]
→ [[mcp-server]]
→ [[mcp-server]]
→ [[CODE]]

## Related notes

→ [[source/engine-cairrn-dispatch]]
→ [[source/engine-cairrn-scheduler]]
→ [[source/engine-phi-session]]
→ [[source/mcp-server-tools-pref

---

## Semantic links

→ [[mcp-server-tools-phi-dispatch]]
→ [[mcp-server-main]]
→ [[mcp-server-server]]
→ [[mcp-server-tools-phi-clip]]
→ [[mcp-server-tools-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-phi-clip-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-state-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
