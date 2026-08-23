# source / mcp-server-tools-init.md

#doc #md

> path: source/mcp-server-tools-init.md  
> ext: .md  

---

# mcp_server/tools/__init__

#code #module #mcp-server #code

> source_path: mcp_server/tools/__init__.py  
> package: mcp_server  
> module: mcp_server/tools/__init__  
> hub: CODE  
> created_ts:   

---

**Package:** `mcp_server`  
**Module:** `mcp_server/tools/__init__`  
**Source:** `mcp_server/tools/__init__.py`

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

→ [[environment]]
→ [[environment]]
→ [[mcp-server]]
→ [[mcp-server]]
→ [[2026-07-13-095004-cairrnify-the-mcp-server-fix-dom-queue-open]]

## Related notes

→ [[source/mcp-server-state]]
→ [[source/mcp-server-main]]
→ [[source/mcp-server-tools-system]]
→ [[source/mcp-server-hooks]]
→ [[source/mcp-server-gate]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[mcp-server-main]]
→ [[mcp-server-server]]
→ [[mcp-index]]
→ [[mcp-server-gate]]
→ [[mcp-server-state]]
→ [[mcp-server-tools-system]]

---

## Semantic links

→ [[mcp-server-server]]
→ [[mcp-server-tools-init]]
→ [[mcp-server-main]]
→ [[mcp-server-state]]
→ [[mcp-server-tools-system]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-modular-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-state-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-cairrn-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
