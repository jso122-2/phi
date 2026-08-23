# source / mcp-server-state.md

#doc #md

> path: source/mcp-server-state.md  
> ext: .md  

---

# mcp_server/_state

#code #module #mcp-server #code

> source_path: mcp_server/_state.py  
> package: mcp_server  
> module: mcp_server/_state  
> hub: CODE  
> created_ts:   

---

**Package:** `mcp_server`  
**Module:** `mcp_server/_state`  
**Source:** `mcp_server/_state.py`

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
                 context manager so tool bodies still execute; state()
                 returns an error payload the agent can act on.
_NullVaultHub  — replaces a failed VaultHub.  All push_* are silent no-ops
                 so tools never crash on backwards-channel writes.

## API

- `class _NullDOMQueue` — Drop-in replacement when spawn_houses() fails at startup.
- `class _NullVaultHub` — Drop-in replacement when open_vault_hub() fails at startup.
- `def _get_vpn_manager` — Return the live VPNManager, creating it on first call.
- `def _get_forecasting_engine` — Lazy-init the ForecastingEngine singleton (shares the global HarmonicIndex).
- `def _mark_startup_complete` — Called by server.py after warmup threads are spawned.

## Internal imports

`sims.harmonic`, `sims.temporal`, `mcp_server.dom_queue`, `mcp_server.vault_hub`, `cognitive.forecasting_engine`, `pipeline.vpn.manager`, `pipeline.vpn.relay_pool`

---

## Semantic links

→ [[environment]]
→ [[environment]]
→ [[2026-07-13-095004-cairrnify-the-mcp-server-fix-dom-queue-open]]
→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]
→ [[mcp-server]]

## Related notes

→ [[source/mcp-server-tools

---

## Semantic links

→ [[mcp-server-server]]
→ [[mcp-server-main]]
→ [[mcp-server-state]]
→ [[mcp-server-tools-system]]
→ [[mcp-server-tools-modular]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-modular-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-temporal-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
