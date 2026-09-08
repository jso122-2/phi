# /wire — Connect the seams

#command #workflow

Read this file immediately and follow its behaviour contract for the rest of this session. Do not skip it.

## Contract

Connect all pieces — imports, config, MCP catalog, tests — then smoke every seam.

## Checklist

- All new modules importable from their package root
- `__init__.py` at every package level exports what consumers need
- No circular imports
- Config values pass through function arguments, not new globals
- Slash aliases (`READ_SUBS` / `DO_SUBS`) match `CATALOG` if you added a command
- End-to-end smoke test passes (`/health`, a read tool, a mutate tool if you touched one)

Prefer MCP `run_command` over Shell for catalog slashes.
