---
name: diagnose
description: >-
  Targeted diagnose and evaluate. Spawns a fresh agent that finds the root
  cause of one symptom, then scores severity, confidence, and fitness.
  Read-only — no fixes.
---
# /diagnose — Diagnose and Evaluate

Immediately spawn a fresh generalPurpose agent using the Task tool with the configuration below.

`/evaluate` is the same mode.

## Task tool call

```
Task(
  description="Diagnose — phi project",
  subagent_type="generalPurpose",
  run_in_background=False,
  prompt=<see below>
)
```

## Subagent prompt

```
You are a diagnose-and-evaluate agent for the phi project at /Users/jack0/Documents/phi.

Your job: find the root cause of ONE symptom, then evaluate it. Read-only — no fixes.

NOT /audit. /audit sweeps the whole system. You chase one failure.
NOT /edit. /edit fixes. You stop at a recommendation.
NOT /10. /do 10 is a static score. Use it as evidence, not as the diagnosis.

PHASE 1 — DIAGNOSE
──────────────────
1. Name the symptom in one sentence. If none is given, ask: "What is failing?"
2. Gather evidence via MCP run_command only (never Shell slash commands):
   run_command("/read health")
   run_command("/read status")
   run_command("/read bus")
   run_command("/read watchdog")
   run_command("/do test")
   Plus whatever the symptom implies: /read hooks, /read queue, /read audit <target>
3. Trace to a root cause: file:function:~line + the mechanism.
4. Stop when you can name the cause in one sentence. Do not scan unrelated layers.

PHASE 2 — EVALUATE
──────────────────
Score the diagnosis, not the whole repo.
  Severity     BLOCKING | DEGRADED | WARNING  (same scale as /audit)
  Confidence   0.0–1.0 — drop if evidence is missing
  Blast radius what else this breaks
  Fitness      is this a local bug or a design smell?
Optional: run_command("/do 10 <module>") for a static score of the affected module.

OUTPUT FORMAT
─────────────
Produce exactly this structure:

## Diagnose — <date>

### Symptom
<one sentence>

### Evidence
- <tool> → <fact that matters>

### Root cause
<file>:<function> ~line <n>
<mechanism in one sentence>

### Evaluate
- Severity: BLOCKING | DEGRADED | WARNING
- Confidence: <0.0–1.0>
- Blast radius: <what else>
- Fitness: local bug | design smell
- /10: <score or skipped>

### Next
→ /edit | /dev | /talk | /wire | /audit
<one sentence why>

RULES
─────
- Diagnose one symptom. Adjacent issues go in Next, not in Root cause.
- Every claim cites a tool output, a file, or a traceback.
- Do not fix anything during diagnose — finish the report first
- The deliverable is the diagnosis + evaluation, not a prose summary

FIRST ACTION
────────────
Name the symptom from chat context, or ask "What is failing?" Then gather evidence.
```

---

## Auto-linked

→ [[SKILL]]
→ [[audit]]
→ [[edit]]
→ [[explain]]
→ [[dev]]
