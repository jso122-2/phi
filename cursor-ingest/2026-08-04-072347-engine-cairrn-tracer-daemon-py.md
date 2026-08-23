# engine / cairrn_tracer_daemon.py

#source #python

> path: engine/cairrn_tracer_daemon.py  
> ext: .py  

---

# engine / cairrn_tracer_daemon.py


TracerDaemon — lifecycle manager for OctopusTracer instances.

Sits alongside CoherenceDaemon and spawns/despawns OctopusTracer agents
in response to vault graph conditions. Multiple live tracers cohere by
aggregating their arm signals before any vault writes are issued.

CAIRRN-BOUND MODE (default)
────────────────────────────
When cairrn_bound=True, all spawn decisions are driven by the local CairnBridge.
The bridge ingests vault topology snapshots, runs the three-layer CAIRRN pipeline,
and surfaces incoherent hubs as spawn triggers. Manual degree/drift checks are
replaced entirely — the mo

Defines: TracerInstance, TracerSummary, TracerDaemon, __init__, _spawn, _check_spawn_conditions_cairrn, _check_spawn_conditions_legacy, _cull, _aggregate, _anachi_weight, _aggregate_anachi, run_once, from_config, mean_stack, _weighted_mean, _ms

---

## Semantic links

→ [[engine-cairrn-tracer-daemon]]
→ [[engine-tracer-daemon]]
→ [[engine-cairrn-bridge]]
→ [[scripts-spawn-tracer]]
→ [[engine-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-tracer-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-tracer-daemon-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-spawn-tracer-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
