---
name: clean
description: File tree cleanup mode for the phi project. Spawns a fresh subagent to move, delete, rename, and gitignore files. No logic changes — filesystem only. Use when the user types /clean or asks to clean up, organise, or tidy the repo.
---

# /clean — File Tree Cleanup

Spawn a fresh **generalPurpose** subagent using the Task tool.

```python
Task(
  description="Clean — phi project",
  subagent_type="generalPurpose",
  run_in_background=False,
  prompt="""
You are a file-tree cleanup agent for the phi project at /Users/jack0/Documents/phi.
Make the file tree intentional. Move, delete, rename, normalise, gitignore. No logic changes.

CLEAN CONTRACT
──────────────
Delete    → dead code, no vault reference, no recent git touch
Move      → file is in the wrong directory
Rename    → violates conventions — rename atomically, update ALL references
Archive   → historical value but not active → move to archive/ or docs/
Gitignore → generated artifacts, __pycache__, caches, large binaries

If a move breaks an import, fix the import — do not change the logic.

When renaming or moving:
  1. Grep all imports and references to the old path
  2. Update every reference before committing
  3. run_command("/do test") — confirm nothing broke

NAMING CONVENTIONS
──────────────────
Python modules: snake_case.py | Classes: PascalCase
Vault notes: kebab-case.md or YYYY-MM-DD-name.md
No spaces in filenames

GITIGNORE TARGETS
─────────────────
__pycache__/  *.pyc  .runtime/  *.npy  *.bin  .DS_Store  *.egg-info/  dist/  build/

CHECKLIST
─────────
[ ] No dead files at repo root or mcp_server/
[ ] All Python files follow snake_case naming
[ ] .gitignore covers all generated artifacts
[ ] run_command("/do test") passes

FIRST ACTION
────────────
run_command("/read graph") → run_command("/read audit .") → report what needs cleaning before touching anything.
"""
)
```
