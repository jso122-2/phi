# source / mcp-server-tools-system.md

#doc #md

> path: source/mcp-server-tools-system.md  
> ext: .md  

---

# mcp_server/tools/system

#code #module #mcp-server #code

> source_path: mcp_server/tools/system.py  
> package: mcp_server  
> module: mcp_server/tools/system  
> hub: CODE  
> created_ts:   

---

**Package:** `mcp_server`  
**Module:** `mcp_server/tools/system`  
**Source:** `mcp_server/tools/system.py`

System / health tools: init_check, system_status, run_tests, hooks, watchdog.

## API

- `def _tool_load_errors` — Return tool-module load failures (populated during tools/__init__ import).
- `def init_check` — Verify that the spotify-rip environment is correctly initialised.
- `def system_status` — One-shot system health report: environment, harmonic index, package versions.
- `def run_tests` — Run the pytest suite and return pass/fail counts.
- `def dom_queue_state` — Inspect the DOM Request Queue — all 6 houses, call counts, and active state.
- `def list_hooks` — Return the current state of the append-only pre-tool hook chain.
- `def register_hook` — Register a named placeholder hook in the append-only hook chain.
- `def watchdog_state` — Inspect the race condition watchdog — stall events, contention events,

## Internal imports

`mcp_server._gate`, `mcp_server._state`, `mcp_server.hooks`, `mcp_server.tools.phi_clip`, `sims.attractors`, `mcp_server`

---

## Semantic links

→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]
→ [[2026-07-21-000947-clean-the-entire-misc-folder-top-to-bottom]]
→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]
→ [[2026-07-16-011935-slash-commands-spotify-rip]]
→ [[2026-07-16-011935-session-init]]

## Related notes

→ [[source/mcp-server-server]]
→ [[source/mcp-server-tools-init]]
→ [[source/mcp-server-state]]
→ [[source/mcp-server-main]]
→ [[source/mcp-server-hooks]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[mcp-server-server]]
→ [[mcp-server-main]]
→ [[mcp-server-tools-init]]
→ [[mcp-index]]
→ [[mcp-server-hooks]]
→ [[mcp-server-gate]]

---

## Semantic links

→ [[mcp-server-main]]
→ [[mcp-server-server]]
→ [[mcp-server-tools-system]]
→ [[mcp-server-tools-modular]]
→ [[mcp-server-tools-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-modular-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-state-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-cairrn-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
