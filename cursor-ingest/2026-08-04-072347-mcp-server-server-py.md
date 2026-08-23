# mcp_server / server.py

#source #python

> path: mcp_server/server.py  
> ext: .py  

---

# mcp_server / server.py


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


Defines: _phi_warmup, _corpus_warmup, _vpn_health_loop, main

---

## Semantic links

→ [[mcp-server-server]]
→ [[mcp-server-tools-system]]
→ [[mcp-server]]
→ [[mcp-server-main]]
→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-server-md]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-init-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-mcp-server-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-gate-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-state-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
