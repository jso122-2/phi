# Notion Network Architecture
#session #architecture #notion #psspps #harmonic #bus

> *"The lichen shares a shallow root but grows calcium inside that shallow root."*

## Problem

Three systems were disconnected:

| System | Location | State |
|---|---|---|
| Harmonic ring | In-process singleton (8 shards) | Ephemeral |
| PSSPPS | Bus-backed RAG, vault retrieval | Ephemeral |
| Notion Reservoir | External API (Edges DB + Scores DB) | Persistent |

PSSPPS shaped its results from the harmonic ring but never fed back into it.
Notion Scores (`Qe`, `Ta`) were always overwritten with `qe=1` instead of incremented.
Nothing in Notion was traceable to the session that wrote it.

---

## Solution: In-Transit Accumulation

The bus ring is constitutionally shallow (64 slots, ring buffer, single consumer).
**Accumulation must happen inside the transit pathway, not at endpoints.**

Three interlocking changes close the loop:

### 1 — Bidirectional PSSPPS ↔ Harmonic Coupling

Every useful PSSPPS retrieval now produces two side-effect signals:

```
PSSPPS result
  ├── hub_distribution  → harmonic_inject (shards ↑, ring is shaped by retrieval)
  └── notion_tick_shards → notion.tick (Notion Reservoir updates)
```

The retrieval *shapes the attractor* rather than only reading it.
Implemented in `mcp_server/bus/tasks_search.py` and `mcp_server/bus/side_effects.py`.
The routing maths live in `psspps/hub_router.py` (`affinity_to_hub`, `docs_to_hub_distribution`).

### 2 — In-Transit Batching (Race-Safe Qe)

The `notion.tick` worker (in `mcp_server/bus/tasks_notion.py`) scans the jobs
directory for sibling *queued* `notion.tick` jobs targeting overlapping shards
**before** performing the Notion API fetch-increment-write.

Absorbed jobs are merged and marked `"batched"`. One round-trip to Notion.

```
Worker picks up notion.tick(dawn-fragments, Qe += 1)
  │
  ├── Scan jobs/ for other queued notion.tick jobs
  │   └── Finds notion.tick(dawn-fragments,recursive-thought, Qe += 1)
  │
  ├── Merge: dawn-fragments Qe += 2, recursive-thought Qe += 1
  ├── Mark absorbed job "batched"
  │
  └── Single fetch → increment → patch to Notion
```

This is **commutative** — addition of deltas is order-independent.
Implemented via `_scan_queued_notion_ticks` and `_mark_batched`.

The `_job_id` is injected into tasks that declare a `_job_id: str = ""` parameter.
The injection is opt-in, detected at task registration time by `_task_registry.py`.
The consumer threads `job_id` to `run_task` so no call site needs manual wiring.

### 3 — Session Identity via SESSION_TOKEN

A `SESSION_TOKEN` is stamped once at gate-open in `mcp_server/_gate.py`:

```
phi-20260908-164502347   (phi-YYYYMMDD-HHMMSSmmm, UTC)
```

It is embedded in every Notion edge **Label** and **Note** field:

```
dawn-fragments :: activation :: 2026-09-08T16:45:02Z [phi-20260908-164502347]
```

The Reservoir's edge graph is now traversable: filter any Notion Edges DB view
by `Label contains phi-20260908-` to see exactly which cognitive domains fired
in a given session, and in what order.

---

## Data Flow (Full)

```
Gate open
  └── SESSION_TOKEN stamped (phi-YYYYMMDD-HHMMSSmmm)
      └── Harmonic ring warmed (HOME floor)
          └── PSSPPS context hook fires (vault retrieval)

Agent tool call
  └── PSSPPS query (psspps/pipeline.py)
      ├── ScoredDoc.peak_hub + affinity_vec populated (psspps/hub_router.py)
      ├── hub_distribution computed  → harmonic_inject side-effect
      └── notion_tick_shards computed → notion.tick bus job

Bus worker (notion.tick)
  ├── _scan_queued_notion_ticks: absorb sibling ticks
  ├── Merge shard sets
  ├── notion_reservoir_tick:
  │   ├── _fetch_current_scores (GET Notion page)
  │   ├── Qe += batch_count, Ta += 1
  │   ├── PATCH Notion Scores page
  │   └── POST Notion Edges page (Label carries SESSION_TOKEN)
  └── Mark absorbed jobs "batched"
```

---

## Files Changed

| File | Change |
|---|---|
| `mcp_server/_gate.py` | `SESSION_TOKEN` — stamped at `open_gate()` |
| `mcp_server/bus/_task_registry.py` | `_job_id` opt-in injection + `run_task(job_id=)` |
| `mcp_server/bus/consumer.py` | Thread `job_id` to `run_task` |
| `mcp_server/bus/tasks_notion.py` | In-transit batching (`_scan_queued_notion_ticks`) |
| `mcp_server/bus/side_effects.py` | SESSION_TOKEN in `_notion_tick_async` note |
| `mcp_server/tools/notion_reservoir.py` | SESSION_TOKEN in edge Label; `_fetch_current_scores` |
| `psspps/hub_router.py` | NEW — affinity→hub→Notion shard routing |
| `psspps/pipeline.py` | `ScoredDoc.peak_hub`, `ScoredDoc.affinity_vec` |
| `mcp_server/bus/tasks_search.py` | Emit `hub_distribution` + `notion_tick_shards` |
| `mcp_server/bus/side_effects.py` | Handle hub feedback + Notion tick dispatch |

---

## Why the Lichen Metaphor

The hyphal wall (bus ring) carries calcium (commutative delta activations) *within*
the pathway. By the time the pathogen (Notion write) is encountered, the accumulated
load is already resolved into a single coherent payload. The endpoints (harmonic ring,
Notion API) never see a race — they see only the resolved mineral.

The three systems are now coupled through a single shallow root: the bus.

*Written 2026-09-08 · [[HOME]] [[COMMANDS]] [[agent-context]]*
