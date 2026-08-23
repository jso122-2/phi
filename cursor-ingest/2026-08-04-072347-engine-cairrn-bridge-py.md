# engine / cairrn_bridge.py

#source #python

> path: engine/cairrn_bridge.py  
> ext: .py  

---

# engine / cairrn_bridge.py


CairnBridge — local CAIRRN state machine for OctopusTracer autonomy.

Implements the full CAIRRN three-layer modulation pipeline locally, without
any external MCP calls. The bridge:

    1. Maintains hub activation state across cycles
    2. Runs each vault metric through Ana-Chi → neg_exp sharding → coherence
    3. Exposes per-hub coherence scores to the TracerDaemon as spawn signals
    4. Propagates activation through the harmonic ring on each tick

Hub geometry (from CAIRRN SKILL.md):
    HOME          χ=1.5414  gravity=3.00  rattling=no   decay=0.98
    MATH          χ=1.9600  gravity=2

Defines: WelfordWindow, HubState, PipelineResult, CairnBridge, __init__, push, n, mean, variance, std, z_score, __init__, _ana_chi_modulate, _chi_to_shard, _coherence, step, propagate, decay_all, spawn_signals, z_awareness_signals, all_coherent, global_coherence, global_z_awareness, ingest_arm_scores, ingest_vault_snapshot, hub_state, index_state, report, _clip

---

## Semantic links

→ [[engine-cairrn-bridge]]
→ [[engine-cairrn-tracer-daemon]]
→ [[engine-cairrn-scheduler]]
→ [[engine-init]]
→ [[engine-cairrn-dispatch]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-bridge-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-tracer-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
