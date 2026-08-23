# models / regression.py

#source #python

> path: models/regression.py  
> ext: .py  

---

# models / regression.py


OctopusTracer Regression Pipeline — closed-form, no learnable parameters.

Steps (ARCHITECTURE LOCKED — pow.md):

    1.  G̅  = complement(G)           ← absence space
    2.  C[u,v] = (h_u·h_v) / (‖h_u‖‖h_v‖τ)  ← SCUP cosine similarity
    3.  Θ  = arccos(clip(C, −1, 1))   ← angular distance
    4.  L̅  = D̅ − Ā̅                   ← complement Laplacian
    5.  F  = L̅ · H                    ← tangent flow
    6.  R  = Θ @ F                    ← regression matrix (MLP input)

All steps are pure numpy — zero learnable parameters.

Input:
    A   ∈ {0,1}^(N×N)   adjacency matrix of the origina

Defines: complement_graph, scup_cosine, angular_dist, complement_laplacian, tangent_flow, regression_matrix, compute_R

---

## Semantic links

→ [[models-regression]]
→ [[models-octopus-head]]
→ [[models-init]]
→ [[models-arms]]
→ [[models-ssm]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-models-regression-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-tracer-arms-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-window-pipeline-py]]
→ [[cursor-ingest/2026-08-04-072347-models-arms-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-octopus-head-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
