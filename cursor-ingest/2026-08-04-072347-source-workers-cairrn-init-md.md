# source / workers-cairrn-init.md

#doc #md

> path: source/workers-cairrn-init.md  
> ext: .md  

---

# workers/cairrn/__init__

#code #module #workers #code

> source_path: workers/cairrn/__init__.py  
> package: workers  
> module: workers/cairrn/__init__  
> hub: CODE  
> created_ts:   

---

**Package:** `workers`  
**Module:** `workers/cairrn/__init__`  
**Source:** `workers/cairrn/__init__.py`

CAIRRN worker system — Coherent Attractor-Indexed Recursive Routing Network.

Ana-Chi modulation · neg_exp sharding · coherence enforcement
+ optional active -Z spatial scoring + mycelial metabolic substrate.

Architecture (SKILL contract)
------------------------------
Every CAIRRN worker belongs to one of the five station hubs.  Each hub is
anchored to an Ana-Chi attractor basin:

    HOME → true_center (1.5414) | MATH → white_peak (1.9600)
    CODE → mirror (0.9900)      | COMMANDS → escape (2.6700)
    agent-context → boundary (0.0300)

Three-layer processing pipeline (SKILL: /cairrn <hub> <metric>):

  ┌─────────────────────────────────────────────────────────────────────────┐
  │  1. Ana-Chi Modulation                                                  │
  │     modulated = metric × gravity × (memory_decay  if rattling)         │
  │     Hub basins: boundary(g=0.50) mirror(g=1.50) true_center(g=3.00)   │
  │                 white_peak(g=2.00) escape(g=1.00)                      │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  2. neg_exp Sharding  ("the backwards e")                               │
  │     shard = floor(e^χ × 8 / 14.44)  clamped [0, 7]                    │
  │     d/dx(−eˣ) = −eˣ — map is closed under differentiation.            │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  3. Coherence Enforcement  ("the negative e")                           │
  │     coherence = exp(−steps / τ)                                        │
  │       steps = |f(χ) − x*|   (neg_exp distance to fixed point)         │
  │       τ     = _TAU = (e^𝒜_χ − W(1)) / W(1) ≈ 7.23                   │
  │

---

## Semantic links

→ [[workers-cairrn-init]]
→ [[pipeline-worker-init]]
→ [[workers-cairrn-worker]]
→ [[pipeline-bridge-init]]
→ [[workers-cairrn-layers]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-worker-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-z-space-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-constants-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-mycelial-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-init-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
