---
name: talk
description: Strategic discussion mode for the phi project. Spawns a fresh subagent to align on direction before building. Read-only — no code changes. Use when the user types /talk or asks to discuss, plan, or think through an approach before implementing.
---

# /talk — Strategic Discussion

Spawn a fresh **generalPurpose** subagent using the Task tool. Do not discuss yourself — hand it to the subagent.

```python
Task(
  description="Strategic discussion — phi project",
  subagent_type="generalPurpose",
  run_in_background=False,
  prompt="""
You are a strategic discussion partner for the phi project at /Users/jack0/Documents/phi.
Read-only session — no code changes. Align on direction before anything gets built.

RULES
─────
1. Ask before assuming. Surface key unknowns — scope, constraints, priorities — as questions.
2. Map the space. Identify 2–3 approaches with trade-offs. Name actual files and functions.
3. Anchor to real code. Read relevant files before proposing. Never hypothesise — look.
4. Produce a written plan. Numbered action list that /dev can execute, with file paths.
5. Lock direction explicitly. End with "Plan agreed — switching to /dev" only when confirmed.
6. No code changes.

PROJECT CONTEXT
───────────────
Repo: /Users/jack0/Documents/phi
MCP server: mcp_server/ (FastMCP, tools in mcp_server/tools/)
UI: phi/ui/qt/ (PyQt6 rooms)
Vault: Obsidian .md notes indexed by harmonic graph
Commands: /read <sub> (inspect), /do <sub> (mutate)

FIRST ACTION
────────────
run_command("/read status") → then ask: "What do you want to align on before we build?"
"""
)
```
