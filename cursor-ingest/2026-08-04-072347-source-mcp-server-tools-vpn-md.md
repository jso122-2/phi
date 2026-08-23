# source / mcp-server-tools-vpn.md

#doc #md

> path: source/mcp-server-tools-vpn.md  
> ext: .md  

---

# mcp_server/tools/vpn

#code #module #mcp-server #code

> source_path: mcp_server/tools/vpn.py  
> package: mcp_server  
> module: mcp_server/tools/vpn  
> hub: CODE  
> created_ts:   

---

**Package:** `mcp_server`  
**Module:** `mcp_server/tools/vpn`  
**Source:** `mcp_server/tools/vpn.py`

mcp_server.tools.vpn — VPN lifecycle tools.

Five MCP tools that expose VPNManager through the standard gate pattern:

    vpn_state      — snapshot + alert ring; init-free (readable at any time)
    vpn_connect    — connect to a relay, apply obfuscation, verify egress
    vpn_verify     — re-run egress consensus check immediately
    vpn_rotate     — disconnect → pick new relay → connect + verify
    vpn_disconnect — graceful teardown

Failure monitoring
------------------
All failures are recorded in the manager's alert ring buffer (last 20 events)
and returned by every tool call via the "alert_ring" key.  Critical failures
(leak, CLI error) are also written to mcp_server._state.startup_errors["vpn_*"]
so they surface in init_check() / system_status() without a dedicated VPN call.

## API

- `def _mgr` — Return the VPNManager singleton, creating it if needed.
- `def _surface_error` — Write a critical error into startup_errors so system_status picks it up.
- `def _clear_error`
- `def vpn_state` — Return the current VPN state snapshot and alert ring.
- `def vpn_connect` — Connect to the VPN.
- `def vpn_verify` — Re-run egress consensus check right now.
- `def vpn_rotate` — Rotate to a new relay.
- `def vpn_disconnect` — Disconnect the VPN and clear state.

## Internal imports

`mcp_server._gate`, `mcp_server._state`

---

## Semantic links

→ [[mcp-server]]
→ [[mcp-server]]
→ [[2026-07-16-011935-mcp-pre-call]]
→ [[2026-07-16-011935-mcp-tool-command-reference]]
→ [[COMMANDS]]

## Related notes

→ [[source/pipeline-vpn-manager]]
→ [[source/mcp-server-gate]]
→ [[source/pipeline-vpn-init]]
→ [[source/mcp-server-server]]
→ [[source/mcp-server-main]]

— import index  

*Imported by

---

## Semantic links

→ [[mcp-server-tools-vpn]]
→ [[mcp-server-server]]
→ [[mcp-server-main]]
→ [[mcp-index]]
→ [[mcp-server-tools-modular]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-cairrn-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-modular-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
