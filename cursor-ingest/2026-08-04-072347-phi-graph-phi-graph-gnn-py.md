# phi / graph / phi_graph_gnn.py

#source #python

> path: phi/graph/phi_graph_gnn.py  
> ext: .py  

---

# phi / graph / phi_graph_gnn.py

phi.graph.phi_graph — PhiGraph: track graph for OctopusTracer ingestion.

Analogous to topology.TopologicalGraph for the Obsidian vault, but built over
Phi's track library using CLAP audio embeddings as node features.

Nodes are tracks.  Edges are implicit — the OctopusTracer uses soft_edge_mode
by default and computes soft edges dynamically from H via sigmoid cosine
similarity, so no explicit adjacency matrix is required.  Call adjacency() only
for full regression mode or external analysis.

Usage
─────
    proj  = CLAPProjection()                          # or load from checkpoint
    graph 

Defines: PhiGraphSnapshot, PhiGraph, index_of, path_of, top_k_similar, coverage_pct, summary, __init__, build, snapshot, adjacency, coverage_report, missing_tracks

---

## Semantic links

→ [[graph-node]]
→ [[engine-vault-garden]]
→ [[graph-init]]
→ [[graph-ingestion]]
→ [[graph-logger]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-builder-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-vault-garden-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-window-pipeline-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
