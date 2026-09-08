# /dev — Build mode

#command #workflow

Read this file immediately and follow its behaviour contract for the rest of this session. Do not skip it.

## Contract

- **Read before write** — inspect the target file first.
- **State then act** — one sentence announcing the next action, then do it.
- **No scope creep** — only what `/talk` (or the user) agreed.
- **Fix broken things** — a linter error from your edit is your bug; fix it before moving on.
- Write, run, iterate, ship. Prefer MCP `run_command` over Shell for catalog slashes.

## Done when

Tests covering the change pass, and the operator can see evidence (test output or a walkthrough).
