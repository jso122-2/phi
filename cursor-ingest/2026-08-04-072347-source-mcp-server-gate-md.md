# source / mcp-server-gate.md

#doc #md

> path: source/mcp-server-gate.md  
> ext: .md  

---

# mcp_server/_gate

#code #module #mcp-server #code

> source_path: mcp_server/_gate.py  
> package: mcp_server  
> module: mcp_server/_gate  
> hub: CODE  
> created_ts:   

---

**Package:** `mcp_server`  
**Module:** `mcp_server/_gate`  
**Source:** `mcp_server/_gate.py`

mcp_server._gate — session gate, init protocol, and requires_init decorator.

The gate opens at server startup via _startup_init (daemon thread at module
import time) if the environment is healthy, or via init_check / system_status.

Protocol constants (PROTOCOL_VERSION, _GATE_CONTRACT_HASH) are Final so any
change is detectable by agents that verify them in their init round-trips.

## API

- `def open_gate` — Mark the session as initialized (call after a successful env check).
- `def is_initialized`
- `def _pre_call` — Session-init gate + pre-hook chain.
- `def requires_init` — Structural session-gate decorator.
- `def _raw_init_check` — Check Python version, required packages, and critical imports.
- `def _startup_init`

## Internal imports

`mcp_server.hooks`

---

## Semantic links

→ [[mcp-server]]
→ [[mcp-server]]
→ [[2026-07-16-011935-agent-initialization-protocol]]
→ [[environment]]
→ [[environment]]

## Related notes

→ [[source/mcp-server-server]]
→ [[source/mcp-server-main]]
→ [[source/mcp-server-tools-init]]
→ [[source/mcp-server-state]]
→ [[source/mcp-server-tools-vpn]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[mcp-server-main]]
→ [[mcp-server-server]]
→ [[mcp-server-tools-init]]
→ [[mcp-index]]
→ [[mcp-server-state]]
→ [[mcp-server-tools-system]]

---

## Semantic links

→ [[mcp-server-server]]
→ [[mcp-server-gate]]
→ [[mcp-server-main]]
→ [[mcp-server-tools-vpn]]
→ [[mcp-server-state]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-state-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-modular-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
