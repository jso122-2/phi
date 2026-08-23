# source / models-regression.md

#doc #md

> path: source/models-regression.md  
> ext: .md  

---

# models/regression

#code #module #models #math

> source_path: models/regression.py  
> package: models  
> module: models/regression  
> hub: MATH  
> created_ts:   

---

**Package:** `models`  
**Module:** `models/regression`  
**Source:** `models/regression.py`

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
    A   ∈ {0,1}^(N×N)   adjacency matrix of the original graph G
    H   ∈ ℝ^(N×d)       hidden states from SSMCore.tick()
    tau ∈ ℝ⁺            temperature from SSMCore

Output:
    R   ∈ ℝ^(N×d)       regression matrix fed to the 8 MLP arms

## API

- `def complement_graph` — Complement adjacency matrix  Ā̅ = (J − I − A),  where
- `def scup_cosine` — SCUP cosine similarity matrix.
- `def angular_dist` — Angular distance  Θ = arccos(clip(C, −1, 1)).
- `def complement_laplacian` — Complement Laplacian  L̅ = D̅ − Ā̅,
- `def tangent_flow` — Tangent flow  F = L̅ · H.
- `def regression_matrix` — Regression matrix  R = Θ @ F.
- `def compute_R` — Run all six pipeline steps and return intermediate tensors.

---

## Semantic links

→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]
→ [[CODE]]
→ [[CODE]]
→ [[MATH]]
→ [[sims]]

## Related notes

→ [[source/models-arms]]
→ [[source/models-octopus-head]]
→ [[source/models-init]]
→ [[source/models-ssm]]
→ [[source/models-suckers]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[models-init]]
→ [[models-octopus-head]]
→ [[models-index]]
→ [[mod

---

## Semantic links

→ [[models-regression]]
→ [[models-octopus-head]]
→ [[models-arms]]
→ [[models-init]]
→ [[models-ssm]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-models-regression-py]]
→ [[cursor-ingest/2026-08-04-072347-source-models-arms-md]]
→ [[cursor-ingest/2026-08-04-072347-source-models-octopus-head-md]]
→ [[cursor-ingest/2026-08-04-072347-source-models-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-models-ssm-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
