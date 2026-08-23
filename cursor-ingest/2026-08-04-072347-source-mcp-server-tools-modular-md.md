# source / mcp-server-tools-modular.md

#doc #md

> path: source/mcp-server-tools-modular.md  
> ext: .md  

---

# mcp_server/tools/modular

#code #module #mcp-server #code

> source_path: mcp_server/tools/modular.py  
> package: mcp_server  
> module: mcp_server/tools/modular  
> hub: CODE  
> created_ts:   

---

**Package:** `mcp_server`  
**Module:** `mcp_server/tools/modular`  
**Source:** `mcp_server/tools/modular.py`

Code-structure tools: code_audit.

Serves both the /modular (packaging) and /refactor (scope analysis) workflows.
All modes are purely read-only static analysis — no files are modified.

## API

- `def _resolve_target` — Resolve a user-supplied target string to an absolute Path.
- `def _python_files` — Return all .py files under path (or just path itself if a file).
- `def _logical_lines` — Count non-empty, non-comment lines.
- `def _audit_inventory` — List every function, class, and module-level constant in the target.
- `def _audit_size` — Walk all .py files under target and flag those that exceed _SIZE_LIMIT.
- `def _audit_imports` — Extract all import statements and flag issues:
- `def _audit_api` — Check what is publicly exported from __init__.py vs. what exists in the package.
- `def code_audit` — /modular + /refactor — static code-structure analysis, read-only.

## Internal imports

`mcp_server._gate`, `mcp_server._state`

---

## Semantic links

→ [[agent-context]]
→ [[agent-context]]
→ [[CODE]]
→ [[CODE]]
→ [[environment]]

## Related notes

→ [[source/mcp-server-tools-init]]
→ [[source/mcp-server-main]]
→ [[source/mcp-server-hooks]]
→ [[source/mcp-server-tools-system]]
→ [[source/mcp-server-state]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[mcp-server-main]]
→ [[mcp-index]]
→ [[mcp-server-tools-init]]
→ [[mcp-server-server]]
→ [[mcp-server-tools-system]]
→ [[mcp-server-tools-forecast]]

---

## Semantic links

→ [[mcp-server-tools-modular]]
→ [[mcp-server-main]]
→ [[mcp-server-server]]
→ [[mcp-server-tools-init]]
→ [[mcp-index]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-cairrn-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-state-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
