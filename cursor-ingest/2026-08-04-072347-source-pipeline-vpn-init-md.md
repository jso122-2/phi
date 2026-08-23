# source / pipeline-vpn-init.md

#doc #md

> path: source/pipeline-vpn-init.md  
> ext: .md  

---

# pipeline/vpn/__init__

#code #module #pipeline #code

> source_path: pipeline/vpn/__init__.py  
> package: pipeline  
> module: pipeline/vpn/__init__  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/vpn/__init__`  
**Source:** `pipeline/vpn/__init__.py`

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

## Internal imports

`pipeline.vpn.egress`, `pipeline.vpn.manager`, `pipeline.vpn.mullvad`, `pipeline.vpn.relay_pool`

---

## Semantic links

→ [[2025-09-09-102444-2025-09-09t20-25-19-520-10-00]]
→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]
→ [[2025-06-08-062508-2025-06-08t16-25-08-874-10-00]]
→ [[2025-08-28-121214-2025-08-28t22-12-14-433-10-00]]
→ [[2026-07-16-011935-vault-coherence-engine]]

## Related notes

→ [[source/pipeline-vpn-relay-pool]]
→ [[source/pipeline-vpn-manager]]
→ [[source/pipeline-vpn-mullvad]]
→ [[source/pipeline-vpn-egress]]
→ [[source/mcp-server-tools-vpn]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[pipeline-vpn-manager]]
→ [[pipeline-vpn-relay-pool]]
→ [[pipeline-index]]
→ [[pipeline-vpn-egress]]
→ [[mcp-server-tools-vpn]]
→ [[pipeline-worker-init]]

---

## Semantic links

→ [[pipeline-vpn-init]]
→ [[pipeline-vpn-manager]]
→ [[scripts-run]]
→ [[pipeline-bridge-init]]
→ [[pipeline-utils-config]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-manager-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-egress-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-relay-pool-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-init-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
