# engine / tracer_daemon.py

#source #python

> path: engine/tracer_daemon.py  
> ext: .py  

---

# engine / tracer_daemon.py


TracerDaemon — manages a pool of OctopusTracers.

Architecture (LOCKED — pow.md):

    Spawn conditions:
      COLD_START       — always fires on first run_once()
      SHARD_DROP       — CAIRRN shard coherence drops below threshold
      DEGREE_ANOMALY   — degree distribution anomaly in complement graph G̅
      EMBEDDING_DRIFT  — BERT embedding drift exceeds threshold
      TICK_GATE        — scheduled tick gate at tick_gate_interval

    max_tracers cap:  hard ceiling on concurrent live tracers

    Tracers cohere by sharing the R signal over the same complement graph slice.

    Ana-Chi w

Defines: Tracer, TracerSummary, _aggregate_tracers, TracerDaemon, step, coherence, as_dict, _mean, __init__, _spawn, _check_degree_anomaly, _check_embedding_drift, _check_shard_drop, run_once, tracers, tick, harmonic_index, bridge, bert, lora_proj, __repr__

---

## Semantic links

→ [[engine-tracer-daemon]]
→ [[engine-cairrn-tracer-daemon]]
→ [[scripts-spawn-tracer]]
→ [[engine-init]]
→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-tracer-daemon-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-tracer-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-spawn-tracer-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-spawn-tracer-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
