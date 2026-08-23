# source / models-octopus-head.md

#doc #md

> path: source/models-octopus-head.md  
> ext: .md  

---

# models/octopus_head

#code #module #models #math

> source_path: models/octopus_head.py  
> package: models  
> module: models/octopus_head  
> hub: MATH  
> created_ts:   

---

**Package:** `models`  
**Module:** `models/octopus_head`  
**Source:** `models/octopus_head.py`

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
G̅ = complement(G).  The result is an N×N attention score matrix.

fs_max = 23.999... (repeating) → clips at FS_MAX_EXCLUSIVE = 24.0 - ε.

This is the canonical entry point:

    from models import OctopusAttentionHead

## API

- `class OctopusAttentionHead` — Bilinear complement-adjacency attention head.

---

## Semantic links

→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]
→ [[pow]]
→ [[sims]]
→ [[sims]]
→ [[HOME]]

## Related notes

→ [[source/models-regression]]
→ [[source/models-arms]]
→ [[source/models-ssm]]
→ [[source/models-init]]
→ [[source/models-suckers]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[models-init]]
→ [[models-index]]
→ [[models-regression]]
→ [[models-arms]]
→ [[models-suckers]]
→ [[models-ssm]]

---

## Semantic links

→ [[models-octopus-head]]
→ [[models-init]]
→ [[models-regression]]
→ [[models-arms]]
→ [[models-ssm]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-models-octopus-head-py]]
→ [[cursor-ingest/2026-08-04-072347-source-models-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-models-arms-md]]
→ [[cursor-ingest/2026-08-04-072347-source-models-regression-md]]
→ [[cursor-ingest/2026-08-04-072347-source-models-ssm-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
