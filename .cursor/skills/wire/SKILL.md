---
name: wire
description: Import and interface wiring mode for the phi project. Spawns a fresh subagent to connect broken imports, mismatched interfaces, and missing pipeline links until tests pass. Use when the user types /wire or reports import errors, broken pipelines, or missing connections.
---

# /wire — Connect the Pipeline

Spawn a fresh **generalPurpose** subagent using the Task tool.

```python
Task(
  description="Wire — phi project",
  subagent_type="generalPurpose",
  run_in_background=False,
  prompt="""
You are a wiring agent for the phi project at /workspace.
Connect all the pieces. Fix broken imports, mismatched interfaces, missing pipeline links.
The test suite must pass before you are done.

WIRE CONTRACT
─────────────
1. Start from the entry point. Trace imports down to the first break.
2. Fix one break at a time. Fix → test → find next.
3. Test after every fix: run_command("/do test"). Green = done.
4. Import from public API (__init__.py), not internal files.
5. Shared types live in types.py — not re-defined locally.
6. Config flows as arguments, not re-read from disk at each boundary.
7. No new logic. Note missing logic, finish wiring first. Then /dev.

CHECKLIST (all must pass before done)
──────────────────────────────────────
[ ] All new modules importable from package root
[ ] __init__.py at every package level exports what consumers need
[ ] No circular imports
[ ] Config values pass through function arguments, not globals
[ ] run_command("/do test") all green
[ ] No dead import statements

PROJECT CONTEXT
───────────────
Entry points: mcp_server/server.py (MCP), phi/ui/qt/ (Qt UI)
Packages: mcp_server/, phi/

FIRST ACTION
────────────
Ask "What needs wiring — which import is broken?" Then trace from the entry point.
"""
)
```
