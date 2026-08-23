# models / octopus_head.py

#source #python

> path: models/octopus_head.py  
> ext: .py  

---

# models / octopus_head.py


OctopusAttentionHead — bilinear complement-adjacency attention.

Formula (ARCHITECTURE LOCKED — pow.md):

    output = Ā̅ @ diag(v_d) @ Ā̅ᵀ − fs

where
    Ā̅   ∈ {0,1}^(N×N)  complement adjacency matrix  (direct MLP input)
    v   ∈ ℝ^N           direction beta vector
    d   ∈ ℝ^N           drift component derivative
    v_d = v ⊙ d         elementwise product → diagonal of the attention kernel
    fs  ∈ ℝ             fixed set scalar, hard-clipped < 24.0 (23.999 recurring)

The operator is matrix multiply.  Ā̅ is the adjacency of the complement graph
G̅ = complement(G).  The result is an N

Defines: OctopusAttentionHead, __init__, forward, set_fs, __repr__

---

## Semantic links

→ [[models-octopus-head]]
→ [[models-arms]]
→ [[engine-gate]]
→ [[models-regression]]
→ [[models-ssm]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-models-octopus-head-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-tracer-arms-py]]
→ [[cursor-ingest/2026-08-04-072347-models-arms-py]]
→ [[cursor-ingest/2026-08-04-072347-models-regression-py]]
→ [[cursor-ingest/2026-08-04-072347-source-models-arms-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
