# source / mcp-server-hooks.md

#doc #md

> path: source/mcp-server-hooks.md  
> ext: .md  

---

# mcp_server/hooks

#code #module #mcp-server #code

> source_path: mcp_server/hooks.py  
> package: mcp_server  
> module: mcp_server/hooks  
> hub: CODE  
> created_ts:   

---

**Package:** `mcp_server`  
**Module:** `mcp_server/hooks`  
**Source:** `mcp_server/hooks.py`

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

Raise `HookViolation` to abort the tool call.
Return None (or implicitly) to allow it.

## API

- `class HookViolation` — Raised by a hook to abort a tool call.
- `class Hook`
- `class HookResult`
- `class HookRegistry` — Append-only hook chain.
- `def _audit_log` — Record every tool call to stderr for MCP output-channel visibility.
- `def _nan_guard` — Reject any tool call whose float arguments contain NaN or Inf.
- `def _param_bounds_guard` — Enforce safe parameter bounds on known numerical arguments.

---

## Semantic links

→ [[mcp-server]]
→ [[mcp-server]]
→ [[2026-07-16-011935-mcp-pre-call]]
→ [[environment]]
→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]

## Related notes

→ [[source/mcp-server-tools-init]]
→ [[source/mcp-server-tools-modular]]
→ [[source/mcp-server-server]]
→ [[source/mcp-server-tools-system]]
→ [[source/mcp-server-gate]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[mcp-server-main]]
→ [[mcp-server-server]]
→ [[mcp-server-tools-init]]
→ [[mcp-index]]
→ [[mcp-server-tools-system]]
→ [[mcp-server-gate]]

---

## Semantic links

→ [[mcp-server-hooks]]
→ [[mcp-server-tools-init]]
→ [[mcp-server-server]]
→ [[mcp-server-tools-modular]]
→ [[mcp-server-tools-system]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-mcp-server-hooks-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-system-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-modular-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
