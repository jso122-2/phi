# mcp_server / hooks.py

#source #python

> path: mcp_server/hooks.py  
> ext: .py  

---

# mcp_server / hooks.py


Append-only pre-tool hook registry.

Design invariants
-----------------
1. Hooks are appended to the chain; never removed, reordered, or cleared.
2. Re-registering a name that already exists is a no-op (idempotent).
3. The chain version equals the current length and only ever increases.
4. Agents may add hooks via the `register_hook` MCP tool; they cannot remove any.
5. Built-in hooks are registered at import time and form the immutable base layer.

Hook contract
-------------
Each hook is a callable with signature:
    fn(tool_name: str, kwargs: dict) -> None

Raise `HookViolation` to abort

Defines: HookViolation, Hook, HookResult, HookRegistry, _audit_log, _nan_guard, _param_bounds_guard, __init__, register, _seal_base, run, state, version, base_version

---

## Semantic links

→ [[mcp-server-hooks]]
→ [[mcp-server-tools-init]]
→ [[mcp-server-gate]]
→ [[mcp-server-dom-queue]]
→ [[mcp-server-tools-modular]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-hooks-md]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-system-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-index-md]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
