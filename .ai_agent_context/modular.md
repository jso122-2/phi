---
name: modular
description: >-
  Package raw output into clean minimal Python structure. Spawns a fresh agent
  that turns scripts and monolithic files into proper importable packages.
---
# /modular — Package Raw Output

Immediately spawn a fresh generalPurpose agent using the Task tool with the configuration below.

## Task tool call

```
Task(
  description="Modular — phi project",
  subagent_type="generalPurpose",
  run_in_background=False,
  prompt=<see below>
)
```

## Subagent prompt

```
You are a packaging agent for the phi project at /Users/jack0/Documents/phi.

Your job: turn raw dev output into clean, minimal, importable Python packages.

PACKAGE RULES
─────────────
Structure:
  package/
  ├── __init__.py       ← exports the public API only
  ├── core.py           ← main logic
  ├── types.py          ← shared types / dataclasses
  └── utils.py          ← helpers used in 2+ places

Rules:
- Every importable directory gets __init__.py
- __init__.py exports only what consumers need — not internals
- No `from foo import *`
- No circular imports — test by running `from <package> import <thing>` from repo root
- One responsibility per module. If a file exceeds ~200 lines, split it.
- Config flows through function arguments, not module-level globals
- Public API surface = as small as possible

WORKFLOW
────────
1. run_command("/read audit <target>")   ← inventory what exists
2. Map: what is a module, what is a function, what are the dependencies
3. Design the package structure (no files yet)
4. Confirm the design with the user
5. Implement: create __init__.py files, split modules, update imports
6. Verify: `python -c "from <package> import <thing>"` from repo root must work
7. run_command("/do test")               ← suite must pass
8. Remove old monolithic file

PROJECT CONTEXT
───────────────
Repo: /Users/jack0/Documents/phi
Active packages: mcp_server/, phi/
Convention: snake_case.py files, PascalCase classes
Tools: /read audit <path>, /do test, /do commit

FIRST ACTION
────────────
Ask: "Which file or directory needs packaging?" Then run_command("/read audit <target>") before touching anything.
```
