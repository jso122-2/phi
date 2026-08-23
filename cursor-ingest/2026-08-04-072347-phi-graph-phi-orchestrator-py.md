# phi / graph / phi_orchestrator.py

#source #python

> path: phi/graph/phi_orchestrator.py  
> ext: .py  

---

# phi / graph / phi_orchestrator.py

phi.graph.phi_orchestrator — end-to-end Phi ↔ OctopusTracer cycle.

PhiOrchestrator ties the full ML pipeline together in a single `run_cycle()`
call.  It is the runtime counterpart of the plan diagram:

    PhiGraph.build()               →  snap.H   (N, 256) CLAP embeddings
    derivative_bridge.score_and_attach() →  snap.d4_scores  (N,)
    PhiGraphBuilder.build_topology()     →  TopologicalGraph (χ, β₀, β₁)
    D4InjectionLayer(H, d4)              →  H_aug  (N, 256)
    OctopusTracer(H_aug)                 →  TracerOutput  (8 arms)
    CoherenceLayer ← topo.invariant.chi  (live topology tar

Defines: PhiOrchestrator, __init__, run_cycle, tracer, bridge, d4_layer, reset_cairrn, parameter_report

---

## Semantic links

→ [[engine-phi-session]]
→ [[engine-vault-garden]]
→ [[engine-mycelial-substrate]]
→ [[models-octopus-head]]
→ [[engine-cairrn-scheduler]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-tracer-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-window-pipeline-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-gnn-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-builder-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
