# phi / graph / phi_tracer_bridge.py

#source #python

> path: phi/graph/phi_tracer_bridge.py  
> ext: .py  

---

# phi / graph / phi_tracer_bridge.py

phi.graph.phi_tracer_bridge — write OctopusTracer arm outputs to Library.annotations.

The bridge is the final step of each PhiOrchestrator cycle.  It takes a
`TracerOutput` and the ordered track `paths` list and writes actionable signals
back into the Phi Library as annotation keys so that the enrichment pipeline,
UI, and smart playlists can act on them.

Written annotation keys (all prefixed `phi_`):
    phi_cluster        int      — argmax cluster assignment (ClusterArm)
    phi_rank           float    — within-cluster relevance score (RankArm)
    phi_prune          float    — deletion can

Defines: PhiTracerBridge, __init__, write, get_prune_candidates, get_resurface_candidates, get_sprout_candidates, get_merge_pairs, annotation_summary, _to_array

---

## Semantic links

→ [[engine-phi-session]]
→ [[engine-init]]
→ [[engine-tracer-daemon]]
→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]
→ [[engine-cairrn-tracer-daemon]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-meta-octopus-arms-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-orchestrator-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-init-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
