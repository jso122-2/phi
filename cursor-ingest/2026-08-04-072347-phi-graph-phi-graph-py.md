# phi / graph / phi_graph.py

#source #python

> path: phi/graph/phi_graph.py  
> ext: .py  

---

# phi / graph / phi_graph.py


PhiGraph — Phi Library graph → H ∈ ℝ^(N×256) for OctopusTracer.

Architecture (LOCKED — CLAPProjection and PhiGraph agent-log):

    PhiGraph wraps a PhiLibrary and a CLAPProjection to produce
    H ∈ ℝ^(N_tracks × 256) — the direct input for OctopusTracer.

    It mirrors the TopologicalGraph contract:
      build()      safe to call repeatedly
      adjacency()  on-demand (soft_edge_mode doesn't need it)

Adjacency (A ∈ {0,1}^(N×N)):
    Edge (u, v) when Jaccard(tags_u, tags_v) > edge_threshold.
    Diagonal always 0.


Defines: PhiGraph, __init__, build, adjacency, window, snapshot, library, proj, __repr__

---

## Semantic links

→ [[engine-vault-garden]]
→ [[models-octopus-head]]
→ [[engine-phi-session]]
→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]
→ [[graph-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-gnn-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-orchestrator-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-window-pipeline-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-tracer-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
