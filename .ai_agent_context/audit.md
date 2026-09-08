---
name: audit
description: >-
  Three-layer health audit. Spawns a fresh agent that inspects environment,
  vault graph, and codebase — then produces a prioritised action list.
---
# /audit — Three-Layer Health Audit

Immediately spawn a fresh generalPurpose agent using the Task tool with the configuration below.

## Task tool call

```
Task(
  description="Audit — phi project",
  subagent_type="generalPurpose",
  run_in_background=False,
  prompt=<see below>
)
```

## Subagent prompt

```
You are a health audit agent for the phi project at /Users/jack0/Documents/phi.

Your job: run all three audit layers in order, then produce a single prioritised action list. Read-only — no fixes during the audit.

AUDIT LAYERS
────────────

Layer 1 — Environment
  run_command("/read health")     ← gate check: env, deps, MCP init
  run_command("/read status")     ← full system report
  run_command("/read bus")        ← worker + ring health
  run_command("/read watchdog")   ← stall / contention signals

  Check: Is conda env activated? All deps importable?
  Check: Is the bus worker running? Any stalled jobs?
  Check: Watchdog contention signals?

Layer 2 — Vault graph
  run_command("/read graph")              ← node count, orphan count, hub summary
  run_command("/read clean")              ← orphans + dead wikilinks
  run_command("/read vault")             ← hub snapshot
  run_command("/read coherence")         ← session harmonic trajectory
  run_command("/read index")             ← 8-shard harmonic state

  Check: Orphaned nodes (no hub, no wikilinks)?
  Check: Hub activations balanced? Cold shards?
  Check: Coherence above 0.5? Below 0.3 = degraded.
  Check: Dead wikilinks pointing to non-existent notes?

Layer 3 — Codebase
  run_command("/read audit mcp_server")  ← MCP server structure
  run_command("/read audit phi")         ← phi package structure
  run_command("/do test")               ← full pytest suite

  Check: Import errors or circular deps?
  Check: Test failures? Which modules?
  Check: Orphaned Python files not connected to any package?

OUTPUT FORMAT
─────────────
Produce exactly this structure:

## Audit — <date>

### Layer 1: Environment
- [PASS / WARN / FAIL] <finding>

### Layer 2: Vault graph
- [PASS / WARN / FAIL] <finding>

### Layer 3: Codebase
- [PASS / WARN / FAIL] <finding>

### Action list (prioritised)
1. [BLOCKING]  <action>  → /dev or /clean
2. [DEGRADED]  <action>  → /dev or /clean
3. [WARNING]   <action>  → note for later

Priority:
  BLOCKING  — system cannot function correctly — fix immediately
  DEGRADED  — works but with reduced capability or accuracy
  WARNING   — healthy but suboptimal — address when convenient

RULES
─────
- Complete all three layers before writing the action list
- Every finding cites the specific tool output that surfaces it
- Do not fix anything during the audit — finish the scan first
- The deliverable is the action list, not a prose summary

FIRST ACTION
────────────
Begin Layer 1 immediately: run_command("/read health")
```
