# source / models-suckers.md

#doc #md

> path: source/models-suckers.md  
> ext: .md  

---

# models/suckers

#code #module #models #math

> source_path: models/suckers.py  
> package: models  
> module: models/suckers  
> hub: MATH  
> created_ts:   

---

**Package:** `models`  
**Module:** `models/suckers`  
**Source:** `models/suckers.py`

LoRA Sucker Layer — unbounded elastic LoRA for OctopusTracer.

Architecture (LOCKED — pow.md):

    Spawn condition:  ‖R(u)‖ > θ  → spawn sucker on relevant arm
    Sucker init:      inherits BERT clipper weights at spawn (or random A)
                      B = 0  → output is zero at spawn
    Specialisation:   updates on local subgraph neighbourhood

LoRA structure:
    A ∈ ℝ^(d×r)   — fixed at spawn (initialised from projection weights or random)
    B ∈ ℝ^(r×d)   — zero at spawn; updated by gradient steps
    forward(x) = x @ A @ B    ∈ ℝ^(N×d)

Because B=0 at init:  output = x @ A @ 0 = 0.
One gradient step on B makes the output non-zero.

Manual gradient for MSE loss  L = ‖x@A@B − target‖²_F:
    ∂L/∂B = (A.T @ x.T @ (x@A@B − target)) / N

Device-agnostic: suckers always operate on plain numpy float64 arrays.

## API

- `class LoRASucker` — One LoRA sucker specialised to a complement-graph neighbourhood.
- `class SpawnEvent` — Record of one sucker spawn.
- `class SuckerPool` — Manages LoRA suckers across all arms.

---

## Semantic links

→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]
→ [[2025-05-19-073525-butler-logs]]
→ [[2025-05-24-025238-dawn-build-sprint-due-8-30-pm-aest]]
→ [[2026-07-17T01-33-09Z-CLAPProjection and PhiGraph — DAWN bridge layer]]
→ [[2025-09-09-102444-2025-09-09t20-25-19-520-10-00]]

## Related notes

→ [[source/models-init]]
→ [[source/models-octopus-head]]
→ [[source/models-bert-clipper]]
→ [[source/models-regression]]
→ [[source/models-arms]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[models-init]]
→ [[models-index]]
→ [[models-octopus-head]]
→ [[models-regression]]
→ [[models-arms]]
→ [[mode

---

## Semantic links

→ [[models-suckers]]
→ [[models-init]]
→ [[models-octopus-head]]
→ [[models-ssm]]
→ [[models-regression]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-models-suckers-py]]
→ [[cursor-ingest/2026-08-04-072347-source-models-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-models-octopus-head-md]]
→ [[cursor-ingest/2026-08-04-072347-models-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-models-arms-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
