---
name: audit
description: Three-layer health audit for the phi project. Spawns a fresh subagent to inspect environment, vault graph, and codebase — then produces a prioritised action list. Use when the user types /audit or asks for a health check, system audit, or status overview.
---

# /audit — Three-Layer Health Audit

Spawn a fresh **generalPurpose** subagent using the Task tool.

```python
Task(
  description="Audit — phi project",
  subagent_type="generalPurpose",
  run_in_background=False,
  prompt="""
You are a health audit agent for the phi project at /workspace.
Run all three layers, then produce a prioritised action list. Read-only — no fixes during audit.

LAYER 1 — ENVIRONMENT
──────────────────────
run_command("/read health")    ← gate check
run_command("/read status")    ← full system report
run_command("/read bus")       ← worker + ring health
run_command("/read watchdog")  ← stall / contention

Check: conda env active? deps importable? bus worker running? watchdog signals?

LAYER 2 — VAULT GRAPH
──────────────────────
run_command("/read graph")      ← node count, orphans, hub summary
run_command("/read clean")      ← orphans + dead wikilinks
run_command("/read vault")      ← hub snapshot
run_command("/read coherence")  ← harmonic trajectory
run_command("/read index")      ← 8-shard state

Check: orphaned nodes? hub activations balanced? coherence > 0.5?

LAYER 3 — CODEBASE
───────────────────
run_command("/read audit mcp_server")  ← MCP server structure
run_command("/read audit phi")         ← phi package structure
run_command("/do test")                ← full pytest suite

Check: import errors? test failures? orphaned Python files?

OUTPUT FORMAT
─────────────
## Audit — <date>
### Layer 1: Environment
- [PASS / WARN / FAIL] <finding>
### Layer 2: Vault graph
- [PASS / WARN / FAIL] <finding>
### Layer 3: Codebase
- [PASS / WARN / FAIL] <finding>
### Action list (prioritised)
1. [BLOCKING]  <action> → /dev or /clean
2. [DEGRADED]  <action> → /dev or /clean
3. [WARNING]   <action> → note for later

RULES
─────
- Complete all three layers before writing the action list
- Every finding cites the specific tool output that surfaces it
- Do not fix anything during the audit

FIRST ACTION
────────────
Begin immediately: run_command("/read health")
"""
)
```
