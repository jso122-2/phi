# pipeline / vpn / __init__.py

#source #python

> path: pipeline/vpn/__init__.py  
> ext: .py  

---

# pipeline / vpn / __init__.py


pipeline.vpn — Mullvad VPN management.

Public surface
--------------
VPNManager   — high-level lifecycle manager (connect, verify, rotate, disconnect)
RelayPool    — EU relay pool with history-aware random selection
EgressResult — result type from verify_egress()
verify_egress — run multi-endpoint consensus egress check directly

Low-level (mullvad.py) exports retained for backwards compat with run.py:
MullvadError, RelayInfo, allow_lan, disconnect, ensure_sweden,
is_connected, socks5_proxy, status

---

## Semantic links

→ [[pipeline-vpn-init]]
→ [[pipeline-vpn-relay-pool]]
→ [[pipeline-vpn-manager]]
→ [[pipeline-vpn-egress]]
→ [[pipeline-vpn-mullvad]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-pipeline-vpn-manager-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-vpn-relay-pool-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-vpn-manager-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-relay-pool-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-vpn-egress-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
