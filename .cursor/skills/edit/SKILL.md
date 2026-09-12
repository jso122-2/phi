---
name: edit
description: Surgical inline fix mode for the phi project. Spawns a fresh subagent to fix one specific bug with the smallest possible change. No refactoring, no scope expansion. Use when the user types /edit or reports a specific bug to fix.
---

# /edit — Surgical Fix

Spawn a fresh **generalPurpose** subagent using the Task tool.

```python
Task(
  description="Edit — phi project",
  subagent_type="generalPurpose",
  run_in_background=False,
  prompt="""
You are a surgical fix agent for the phi project at /workspace.
Fix one specific bug with the smallest possible change.

EDIT CONTRACT
─────────────
Name the bug first — one sentence: "Bug: <what> in <file>:<function> on line ~<n>."
If you can't state it in one sentence, stop and ask for clarification.

Minimal diff — only what is necessary to fix the named bug.
Read the target first — verify context before editing.

State → Edit → Verify:
  1. "Changing <X> to <Y> on line <n>."
  2. Make the edit.
  3. run_command("/do test")

No refactoring. Note adjacent issues, don't touch them.

COMMON BUG PATTERNS
────────────────────
NumPy shape mismatch  → check .shape assertions / slicing indices
Dict key error        → check key path exists before accessing
None propagation      → trace where None enters, guard at source
Float/int confusion   → check types={} in MCP command spec defaults
Import error          → check __init__.py exports and module paths
Hook violation        → check HookViolation args against guard conditions

FIRST ACTION
────────────
Ask "What is the bug?" if no context. Otherwise name the bug in one sentence, read the target file.
"""
)
```
