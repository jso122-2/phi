# pipeline / vpn / manager.py

#source #python

> path: pipeline/vpn/manager.py  
> ext: .py  

---

# pipeline / vpn / manager.py


pipeline.vpn.manager — VPNManager: full lifecycle, health monitoring, kill switch.

Architecture
------------
VPNManager is a thread-safe singleton that drives the complete VPN session:

    connect(relay=None)   pick relay from pool (or use explicit hostname),
                          apply obfuscation, connect, verify egress, record event
    verify()              re-run multi-endpoint egress consensus check
    rotate()              disconnect → pick new relay → connect + verify
    disconnect()          graceful teardown, clear state
    health_check()        one health cycle: verify if 

Defines: VPNStatus, VPNManager, _utc_now, __init__, connect, verify, rotate, disconnect, health_check, state_dict, _set_status, _record

---

## Semantic links

→ [[pipeline-vpn-manager]]
→ [[pipeline-vpn-init]]
→ [[mcp-server-tools-vpn]]
→ [[pipeline-vpn-relay-pool]]
→ [[pipeline-vpn-egress]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-pipeline-vpn-init-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-vpn-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-manager-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-vpn-manager-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-relay-pool-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
