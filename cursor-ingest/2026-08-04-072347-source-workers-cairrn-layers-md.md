# source / workers-cairrn-layers.md

#doc #md

> path: source/workers-cairrn-layers.md  
> ext: .md  

---

# workers/cairrn/layers

#code #module #workers #code

> source_path: workers/cairrn/layers.py  
> package: workers  
> module: workers/cairrn/layers  
> hub: CODE  
> created_ts:   

---

**Package:** `workers`  
**Module:** `workers/cairrn/layers`  
**Source:** `workers/cairrn/layers.py`

CAIRRN three-layer pipeline dataclasses and runner functions.

Layer 1 — Ana-Chi Modulation   : ModulationResult, ana_chi_modulate
Layer 2 — neg_exp Sharding     : ShardSignal, neg_exp_shard
Layer 3 — Coherence Enforcement: CoherenceResult, measure_coherence

## API

- `class ModulationResult` — Output of Ana-Chi modulation for one worker metric.
- `def ana_chi_modulate` — Apply Ana-Chi basin modulation to a worker metric.
- `class ShardSignal` — Shard assignment derived from one step of f(x) = −eˣ on basin χ.
- `def neg_exp_shard` — Run neg_exp analysis on the hub's Ana-Chi basin χ to produce a ShardSignal.
- `class CoherenceResult` — Layer 3 — Coherence Enforcement ("the negative e").
- `def measure_coherence` — Layer 3 — Coherence Enforcement.

## Internal imports

`sims.ana_chi`, `sims.attractors`, `workers.cairrn._constants`

---

## Semantic links

→ [[2026-07-16-011935-cairrn-cairrn-worker-system]]
→ [[cairrn]]
→ [[workers]]
→ [[HOME]]
→ [[workers]]

## Related notes

→ [[source/workers-cairrn-init]]
→ [[source/workers-cairrn-worker]]
→ [[source/workers-cairrn-formulas]]
→ [[source/engine-cairrn-bridge]]
→ [[source/engine-cairrn-scheduler]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[workers-cairrn-z-space]]
→ [[workers-index]]
→ [[workers-cairrn-worker]]
→ [[workers-cairrn-init]]
→ [[workers-cairrn-formulas]]
→ [[workers-cairrn-constants]]

---

## Semantic links

→ [[workers-cairrn-layers]]
→ [[workers-cairrn-worker]]
→ [[pipeline-worker-init]]
→ [[workers-base]]
→ [[workers-cairrn-desktop]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-worker-md]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-init-md]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-layers-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-constants-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
