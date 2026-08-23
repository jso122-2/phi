# mcp_server / tools / phi_dispatch.py

#source #python

> path: mcp_server/tools/phi_dispatch.py  
> ext: .py  

---

# mcp_server / tools / phi_dispatch.py


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
  - _harm

Defines: _get_dispatcher, phi_enqueue, phi_step, phi_queue, phi_flush

---

## Semantic links

→ [[mcp-server-tools-phi-dispatch]]
→ [[engine-cairrn-dispatch]]
→ [[engine-cairrn-scheduler]]
→ [[mcp-server-gate]]
→ [[engine-phi-player]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-scheduler-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-router-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-dispatch-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-phi-dispatch-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
