# mcp_server / _state.py

#source #python

> path: mcp_server/_state.py  
> ext: .py  

---

# mcp_server / _state.py


mcp_server._state — process-lifetime singletons.

All stateful objects that are shared across tool modules live here.
Import from this module; never construct a second instance anywhere.

Startup resilience
------------------
Every singleton initialisation is wrapped in try-except.  A failed init is
recorded in `startup_errors` (visible via init_check / system_status) and a
null-stub is assigned so that the module always imports cleanly.

Null stubs
----------
_NullDOMQueue  — replaces a failed DOMRequestQueue.  gate() is a no-op
                 context manager so tool bodies still execute; 

Defines: _NullDOMQueue, _NullVaultHub, _get_vpn_manager, _get_forecasting_engine, _mark_startup_complete, gate, state, house_for, __init__, push_harmonic, push_sim, push_queue, push_forecast, push_all

---

## Semantic links

→ [[mcp-server-state]]
→ [[mcp-server-tools-init]]
→ [[mcp-server-gate]]
→ [[mcp-server-server]]
→ [[mcp-server-tools-system]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-init-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-gate-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-state-md]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-system-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
