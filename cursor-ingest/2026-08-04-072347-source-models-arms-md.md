# source / models-arms.md

#doc #md

> path: source/models-arms.md  
> ext: .md  

---

# models/arms

#code #module #models #math

> source_path: models/arms.py  
> package: models  
> module: models/arms  
> hub: MATH  
> created_ts:   

---

**Package:** `models`  
**Module:** `models/arms`  
**Source:** `models/arms.py`

OctopusTracer MLP Arms — 8 heads operating on the regression matrix R.

Architecture (LOCKED — pow.md):

    8 arms: PRUNE, GRAFT, CLUSTER, RANK, TAG, RESURFACE, MERGE, SPROUT

    Each arm:   R → [Linear(d, d_hidden) → ReLU → Linear(d_hidden, 1)] → score

    Input:  R ∈ ℝ^(N×d)     regression matrix from regression.py
    Output: scores ∈ ℝ^N    per-node arm score

Parameter budget:
    d=256, d_hidden=256
    per arm: W1 (256×256=65536) + b1 (256) + W2 (256×1=256) + b2 (1) = 66,049
    8 arms: ~528,392  ≈ 400K target (slight over; acceptable)

## API

- `class ArmScores` — Per-arm score vectors for one forward pass.
- `class MLPArm` — Single MLP arm.
- `class OctopusArms` — All 8 MLP arms bundled together.

---

## Semantic links

→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]
→ [[CODE]]
→ [[CODE]]
→ [[FORMULAS]]
→ [[2025-12-13-062815-miler-coat-of-arms]]

## Related notes

→ [[source/models-regression]]
→ [[source/models-octopus-head]]
→ [[source/models-init]]
→ [[source/engine-bridge-factory]]
→ [[source/models-suckers]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[models-init]]
→ [[models-index]]
→ [[models-regression]]
→ [[models-octopus-head]]
→ [[models-bert-clipper]]
→ [[models-ssm]]

---

## Semantic links

→ [[models-arms]]
→ [[models-octopus-head]]
→ [[models-init]]
→ [[models-regression]]
→ [[engine-bridge-factory]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-models-arms-py]]
→ [[cursor-ingest/2026-08-04-072347-source-models-regression-md]]
→ [[cursor-ingest/2026-08-04-072347-source-models-octopus-head-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-tracer-arms-py]]
→ [[cursor-ingest/2026-08-04-072347-source-models-index-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
