# source / pipeline-vpn-manager.md

#doc #md

> path: source/pipeline-vpn-manager.md  
> ext: .md  

---

# pipeline/vpn/manager

#code #module #pipeline #code

> source_path: pipeline/vpn/manager.py  
> package: pipeline  
> module: pipeline/vpn/manager  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/vpn/manager`  
**Source:** `pipeline/vpn/manager.py`

pipeline.vpn.manager — VPNManager: full lifecycle, health monitoring, kill switch.

Architecture
------------
VPNManager is a thread-safe singleton that drives the complete VPN session:

    connect(relay=None)   pick relay from pool (or use explicit hostname),
                          apply obfuscation, connect, verify egress, record event
    verify()              re-run multi-endpoint egress consensus check
    rotate()              disconnect → pick new relay → connect + verify
    disconnect()          graceful teardown, clear state
    health_check()        one health cycle: verify if due, abort on leak

The manager maintains an alert ring buffer (last 20 events) that is the
primary monitoring surface exposed via the MCP vpn_state tool.

State machine
-------------
    DISCONNECTED → CONNECTING → VERIFYING → CONNECTED
                                                ↓
                                           ROTATING (relay swap in-progress)
                                                ↓
                                           VERIFYING → CONNECTED
    Any state → LEAKED   (egress check shows non-Mullvad IP)
    Any state → ERROR    (CLI failure or timeout)

## API

- `class VPNStatus`
- `class VPNManager` — Thread-safe VPN lifecycle manager.
- `def _utc_now`

## Internal imports

`pipeline.vpn.egress`, `pipeline.vpn.mullvad`, `pipeline.vpn.relay_pool`

---

## Semantic links

→ [[2025-09-09-102444-2025-09-09t20-25-19-520-10-00]]
→ [[CODE]]
→ [[CODE]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]

## Related notes

→ [[source/pipeline-vpn-init]]
→ [[source/mcp-server-tools-vpn]]
→ [[

---

## Semantic links

→ [[pipeline-vpn-manager]]
→ [[pipeline-vpn-init]]
→ [[scripts-run]]
→ [[mcp-server-tools-vpn]]
→ [[pipeline-vpn-mullvad]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-egress-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-vpn-manager-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-relay-pool-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-vpn-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
