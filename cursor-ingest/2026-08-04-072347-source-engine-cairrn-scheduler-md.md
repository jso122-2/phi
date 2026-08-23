# source / engine-cairrn-scheduler.md

#doc #md

> path: source/engine-cairrn-scheduler.md  
> ext: .md  

---

# engine/cairrn_scheduler

#code #module #engine #code

> source_path: engine/cairrn_scheduler.py  
> package: engine  
> module: engine/cairrn_scheduler  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/cairrn_scheduler`  
**Source:** `engine/cairrn_scheduler.py`

CAIRRNScheduler — CAIRRN-bound tick gate for PhiTracerSession.

Architecture
------------
The scheduler sits between the caller and PhiTracerSession.  Every `step()`
call goes through a coherence gate derived from the CODE hub's harmonic
shard activations (shards 3 and 4 — RANK and TAG arms).

Gate formula (mirrors engine/gate.py and the CAIRRN SKILL contract):

    code_activation = mean(shard[3].activation, shard[4].activation)
    coherence       = exp(−steps_since_tick / tau)
    gate_open       = coherence ≥ COHERENCE_THRESHOLD  (≈ 0.5671)

When the gate is open → tick (or refresh_and_tick) runs and steps resets.
When the gate is closed → tick is skipped; steps_since_tick increments.

The CODE hub is the scheduling signal because RANK (shard 3) and TAG (shard 4)
measure the quality of the current graph clustering and annotation state.
Low CODE activation means the system hasn't fully settled after the last
topology change — ticking too early would amplify noise.

Refresh policy
--------------
`refresh_every` controls how many successful (gated) ticks trigger a full
`refresh_and_tick()` instead of a plain `tick()`.  Set to 0 to never
auto-refresh (caller triggers refresh manually via `step(force_refresh=True)`).

SchedulerResult
---------------
Every `step()` returns a SchedulerResult regardless of gate outcome:

    gated           : True if a tick actually ran
    skipped         : True if coherence was below threshold
    coherence       : float in (0, 1] — the gate coherence at step time
    code_activation : mean CODE hub shard activation (gate signal)
    steps_since_tick: steps elapsed since the last successful tick
    refresh_ran     : True if this tick was a

---

## Semantic links

→ [[engine-cairrn-scheduler]]
→ [[engine-cursor-tracer]]
→ [[mcp-server-tools-cairrn]]
→ [[engine-index]]
→ [[engine-cairrn-dispatch]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-tracer-daemon-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-dispatch-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-worker-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
