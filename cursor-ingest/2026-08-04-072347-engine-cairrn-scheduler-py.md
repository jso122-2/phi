# engine / cairrn_scheduler.py

#source #python

> path: engine/cairrn_scheduler.py  
> ext: .py  

---

# engine / cairrn_scheduler.py


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

When the gate is open → tick (or refresh_and_ti

Defines: SchedulerResult, CAIRRNScheduler, make_cairrn_scheduler, as_dict, __init__, step, force_tick, steps_since_tick, ticks_run, coherence, reset_steps, state, _read_code_activation, __repr__

---

## Semantic links

→ [[engine-cairrn-scheduler]]
→ [[engine-cairrn-dispatch]]
→ [[engine-cairrn-tracer-daemon]]
→ [[engine-cairrn-bridge]]
→ [[engine-gate]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-router-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-phi-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-watchdog-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
