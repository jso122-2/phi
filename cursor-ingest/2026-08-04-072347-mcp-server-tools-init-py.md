# mcp_server / tools / __init__.py

#source #python

> path: mcp_server/tools/__init__.py  
> ext: .py  

---

# mcp_server / tools / __init__.py


mcp_server.tools — MCP tool registry.

Importing this package triggers all @mcp.tool() registrations.

Startup resilience
------------------
Each tool module is loaded individually inside try-except so that a single
broken module (bad import, missing dependency, syntax error) cannot prevent
the rest from registering.  Failed modules are recorded in `load_errors` and
surfaced via init_check() / system_status().

---

## Semantic links

→ [[mcp-server-tools-init]]
→ [[mcp-server-state]]
→ [[mcp-server-tools-modular]]
→ [[mcp-server-tools-system]]
→ [[mcp-server-main]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-mcp-server-state-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-modular-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
