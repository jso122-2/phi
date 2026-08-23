# engine / coherence_daemon.py

#source #python

> path: engine/coherence_daemon.py  
> ext: .py  

---

# engine / coherence_daemon.py


CoherenceDaemon — main orchestration loop for the vault coherence engine.

Each cycle:
    1. orch.refresh()          — re-encode all notes in the vault
    2. topo.build()            — recompute topology primitives (V, E, T, χ, β₀, β₁)
    3. HealthLog.append()      — persist the topology snapshot
    4. OrphanDetector.scan()   — find weakly-clustered notes
    5. VaultWriter.append_links() for each orphan's suggestions
    6. BridgeFactory.scan()    — find isolated cluster pairs
    7. VaultWriter.create_bridge_note() for each bridge spec
    8. MycelialNetwork.decay_all() — every decay_int

Defines: _graph_snapshot, CoherenceDaemon, _parse_args, main, __init__, run_once, run_loop

---

## Semantic links

→ [[engine-coherence-daemon]]
→ [[engine-vault-garden]]
→ [[engine-vault-writer]]
→ [[engine-health-log]]
→ [[engine-arm-injector]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-coherence-daemon-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-health-log-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-orphan-detector-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-vault-garden-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-vault-writer-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
