# /audit — Three-layer health

#command #workflow

Read this file immediately and follow its behaviour contract for the rest of this session. Do not skip it.

## Contract

Full health audit: vault graph + codebase + environment.
Output a `CRITICAL → HIGH → MEDIUM → LOW → PASS` report.
Wait for confirmation before fixing anything.

## Calls (read-only first)

1. MCP `run_command` `/read graph`
2. MCP `run_command` `/read clean`  (orphans + dead wikilinks)
3. MCP `run_command` `/read health`
4. MCP `run_command` `/read status`
5. pytest (MCP `/do test` or `run_tests`)
6. mypy if the environment has it

Do not apply fixes until the operator says so.
