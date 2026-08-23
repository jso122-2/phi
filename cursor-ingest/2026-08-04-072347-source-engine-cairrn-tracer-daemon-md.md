# source / engine-cairrn-tracer-daemon.md

#doc #md

> path: source/engine-cairrn-tracer-daemon.md  
> ext: .md  

---

# engine/cairrn_tracer_daemon

#code #module #engine #code

> source_path: engine/cairrn_tracer_daemon.py  
> package: engine  
> module: engine/cairrn_tracer_daemon  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/cairrn_tracer_daemon`  
**Source:** `engine/cairrn_tracer_daemon.py`

TracerDaemon — lifecycle manager for OctopusTracer instances.

Sits alongside CoherenceDaemon and spawns/despawns OctopusTracer agents
in response to vault graph conditions. Multiple live tracers cohere by
aggregating their arm signals before any vault writes are issued.

CAIRRN-BOUND MODE (default)
────────────────────────────
When cairrn_bound=True, all spawn decisions are driven by the local CairnBridge.
The bridge ingests vault topology snapshots, runs the three-layer CAIRRN pipeline,
and surfaces incoherent hubs as spawn triggers. Manual degree/drift checks are
replaced entirely — the model is autonomous.

Spawn conditions in CAIRRN-bound mode:
    HUB_INCOHERENT  — any CAIRRN hub drops below coherence_floor
    TICK_GATE       — every tick_gate_every cycles regardless

LEGACY MODE (cairrn_bound=False)
──────────────────────────────────
Manual conditions (degree anomaly, BERT drift) are still supported for
ablation studies or environments where CAIRRN is not active.

Swarm coherence:
    Multiple live tracers mean-aggregate their write-gated arm outputs.
    Tracers are culled after cull_after_readonly_ticks consecutive read-only cycles.

Integration:
    tracer_daemon = TracerDaemon.from_config(cfg)
    summary = tracer_daemon.run_once(snapshot, H)  ← adj not needed in soft_edge_mode

## API

- `class TracerInstance` — Wraps a single live OctopusTracer with its lifecycle metadata.
- `class TracerSummary` — Summary returned to CoherenceDaemon after one tracer daemon cycle.
- `class TracerDaemon` — Manages a swarm of OctopusTracer instances in sync with CAIRRN tick cycles.

## Internal imports

`models.octopus_tracer`, `engine.cairrn_bridge`

---

#

---

## Semantic links

→ [[engine-cairrn-tracer-daemon]]
→ [[engine-tracer-daemon]]
→ [[engine-cursor-tracer]]
→ [[engine-init]]
→ [[scripts-spawn-tracer]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-scheduler-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-dispatch-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-cairrn-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
