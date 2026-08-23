# source / engine-tracer-daemon.md

#doc #md

> path: source/engine-tracer-daemon.md  
> ext: .md  

---

# engine/tracer_daemon

#code #module #engine #code

> source_path: engine/tracer_daemon.py  
> package: engine  
> module: engine/tracer_daemon  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/tracer_daemon`  
**Source:** `engine/tracer_daemon.py`

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

    Ana-Chi weight:   decreases with tick (rattling decay property from ana_chi.py)

    CAIRRN routing:   arm scores routed to harmonic index via CAIRRNBridge after
                      every run_once() — index changes after each call.

TracerSummary
    Aggregates across all live tracers:
      arm_prune, arm_graft, arm_cluster, arm_rank,
      arm_tag, arm_resurface, arm_merge, arm_sprout
      aggregated_tag, aggregated_merge   (mean over all tracer × tag/merge scores)
      mean_tick

## API

- `class Tracer` — One OctopusTracer instance.
- `class TracerSummary` — Aggregated view across all live tracers after one run_once() pass.
- `def _aggregate_tracers`
- `class TracerDaemon` — Manages the pool of live OctopusTracers.

## Internal imports

`models.arms`, `models.bert_clipper`, `models.regression`, `models.ssm`, `engine.gate`, `sims.harmonic`, `engine.bridge_factory`, `engine.vault_writer`

---

## Semantic links

→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]
→ [[2025-05-27-174633-2025-05-28t03-46-33-990-10-00]]
→ [[2026-07-16-011935-cairrn-cairrn-worker-system]]
→ [[2025-09-09-10

---

## Semantic links

→ [[engine-tracer-daemon]]
→ [[engine-cairrn-tracer-daemon]]
→ [[scripts-spawn-tracer]]
→ [[engine-init]]
→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-tracer-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-spawn-tracer-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-init-py]]
→ [[cursor-ingest/2026-08-04-072347-scripts-spawn-tracer-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-tracer-daemon-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
