# source / engine-coherence-daemon.md

#doc #md

> path: source/engine-coherence-daemon.md  
> ext: .md  

---

# engine/coherence_daemon

#code #module #engine #code

> source_path: engine/coherence_daemon.py  
> package: engine  
> module: engine/coherence_daemon  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/coherence_daemon`  
**Source:** `engine/coherence_daemon.py`

CoherenceDaemon — main orchestration loop for the vault coherence engine.

Each cycle:
    1. orch.refresh()          — re-encode all notes in the vault
    2. topo.build()            — recompute topology primitives (V, E, T, χ, β₀, β₁)
    3. HealthLog.append()      — persist the topology snapshot
    4. OrphanDetector.scan()   — find weakly-clustered notes
    5. VaultWriter.append_links() for each orphan's suggestions
    6. BridgeFactory.scan()    — find isolated cluster pairs
    7. VaultWriter.create_bridge_note() for each bridge spec
    8. MycelialNetwork.decay_all() — every decay_interval_cycles cycles (C-layer)
    9. sleep(interval_seconds)

Topology is driven through TopologicalGraph (topology.topo_graph), which
decomposes the nx.DiGraph into Vertex / Edge / Triangle primitives and
computes the full suite of topological invariants (χ, β₀, β₁).  The
CoherenceLayer in models/coherence.py uses the current χ value from this
graph as its Euler-characteristic target each cycle.

CLI:
    python -m engine.coherence_daemon [options]

    --checkpoint PATH   Path to model checkpoint (auto-detected if omitted)
    --config PATH       Path to config.yaml
    --interval N        Seconds between cycles (default: 300)
    --dry-run           Log actions without writing to the vault
    --once              Run one cycle and exit (ignores --interval)
    --orphan-threshold          Cluster score below which a note is an orphan (default: 0.15)
    --min-bridges               Min inter-cluster wikilinks before bridging (default: 1)
    --top-k-links               Link suggestions per orphan (default: 5)
    --log-level                 Logging level (default: INFO)
    --no-mycel

---

## Semantic links

→ [[engine-coherence-daemon]]
→ [[engine-vault-garden]]
→ [[engine-cairrn-tracer-daemon]]
→ [[engine-vault-writer]]
→ [[mcp-server-vault-hub]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-coherence-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-vault-garden-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-gate-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-vault-writer-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-vault-hub-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
