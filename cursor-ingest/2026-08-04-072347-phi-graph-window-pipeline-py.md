# phi / graph / _window_pipeline.py

#source #python

> path: phi/graph/_window_pipeline.py  
> ext: .py  

---

# phi / graph / _window_pipeline.py

phi.graph._window_pipeline — list[SongNode] → regression tensors.

Bridges the phi graph layer to the OctopusTracer regression pipeline.

The regression pipeline (models/regression.py) needs three things:

    A     ∈ {0,1}^(N×N)   adjacency of G (window-local)
    H     ∈ ℝ^(N×d)       hidden states per node
    tau   ∈ ℝ⁺            temperature

This module produces all three from a list[SongNode] returned by
PhiGraphSnapshot.window() or build_window().

Public API
----------
    tensors = build_window_tensors(nodes)
        → WindowTensors(A, A_bar, H_phi)

    result  = run_window(nodes, s

Defines: WindowTensors, WindowResult, _complement, _audio_adjacency, build_window_tensors, run_window, N

---

## Semantic links

→ [[engine-vault-garden]]
→ [[models-octopus-head]]
→ [[models-regression]]
→ [[models-ssm]]
→ [[models-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-gnn-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-metadata-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-init-py]]
→ [[cursor-ingest/2026-08-04-072347-models-regression-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
