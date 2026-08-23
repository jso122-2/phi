# mcp_server / _gate.py

#source #python

> path: mcp_server/_gate.py  
> ext: .py  

---

# mcp_server / _gate.py


mcp_server._gate — session gate, init protocol, and requires_init decorator.

The gate opens at server startup via _startup_init (daemon thread at module
import time) if the environment is healthy, or via init_check / system_status.

Protocol constants (PROTOCOL_VERSION, _GATE_CONTRACT_HASH) are Final so any
change is detectable by agents that verify them in their init round-trips.


Defines: open_gate, is_initialized, _pre_call, requires_init, _raw_init_check, _startup_init, _gated

---

## Semantic links

→ [[mcp-server-gate]]
→ [[mcp-server-server]]
→ [[mcp-server-state]]
→ [[mcp-server-tools-init]]
→ [[mcp-server-dom-queue]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-gate-md]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-state-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-system-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-vpn-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
