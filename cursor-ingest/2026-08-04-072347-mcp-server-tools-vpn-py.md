# mcp_server / tools / vpn.py

#source #python

> path: mcp_server/tools/vpn.py  
> ext: .py  

---

# mcp_server / tools / vpn.py


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
and returned by every tool call via the "a

Defines: _mgr, _surface_error, _clear_error, vpn_state, vpn_connect, vpn_verify, vpn_rotate, vpn_disconnect

---

## Semantic links

→ [[mcp-server-tools-vpn]]
→ [[pipeline-vpn-manager]]
→ [[pipeline-vpn-init]]
→ [[mcp-server-gate]]
→ [[mcp-server-server]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-pipeline-vpn-manager-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-vpn-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-vpn-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-manager-md]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-gate-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
