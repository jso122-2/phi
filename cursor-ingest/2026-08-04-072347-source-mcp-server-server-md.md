# source / mcp-server-server.md

#doc #md

> path: source/mcp-server-server.md  
> ext: .md  

---

# mcp_server/server

#code #module #mcp-server #code

> source_path: mcp_server/server.py  
> package: mcp_server  
> module: mcp_server/server  
> hub: CODE  
> created_ts:   

---

**Package:** `mcp_server`  
**Module:** `mcp_server/server`  
**Source:** `mcp_server/server.py`

spotify-rip MCP server — entry point.

Architecture
------------
mcp_server/_state.py  — singletons (mcp, harmonic index, dom queue, vault hub)
mcp_server/_gate.py   — session gate, requires_init, init protocol constants
mcp_server/tools/     — one module per tool domain; importing registers @mcp.tool()

Start with:
    python -m mcp_server.server
or via the console script:
    spotify-rip-mcp

## API

- `def _phi_warmup` — Pre-warm the PhiTracerSession + GeminiClipper at server spawn.
- `def _corpus_warmup` — Pre-warm the VaultCorpus cache at server spawn.
- `def _vpn_health_loop` — Background VPN health monitor.
- `def main`

## Internal imports

`mcp_server.tools`, `mcp_server._state`, `mcp_server.tools.phi_clip`, `psspps.retriever`

---

## Semantic links

→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]
→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]
→ [[mcp-server]]
→ [[2026-07-16-011935-agent-initialization-protocol]]
→ [[2026-07-16-011935-session-init]]

## Related notes

→ [[source/mcp-server-tools-system]]
→ [[source/mcp-server-main]]
→ [[source/mcp-server-gate]]
→ [[source/mcp-server-state]]
→ [[source/mcp-server-hooks]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[mcp-server-main]]
→ [[mcp-index]]
→ [[mcp-server-tools-init]]
→ [[mcp-server-gate]]
→ [[mcp-server-tools-system]]
→ [[mcp-server-state]]

---

## Semantic links

→ [[mcp-server-server]]
→ [[mcp-server-tools-system]]
→ [[mcp-server]]
→ [[mcp-server-main]]
→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-mcp-server-server-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-state-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
