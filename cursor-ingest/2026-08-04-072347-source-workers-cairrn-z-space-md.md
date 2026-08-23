# source / workers-cairrn-z-space.md

#doc #md

> path: source/workers-cairrn-z-space.md  
> ext: .md  

---

# workers/cairrn/z_space

#code #module #workers #code

> source_path: workers/cairrn/z_space.py  
> package: workers  
> module: workers/cairrn/z_space  
> hub: CODE  
> created_ts:   

---

**Package:** `workers`  
**Module:** `workers/cairrn/z_space`  
**Source:** `workers/cairrn/z_space.py`

CAIRRN active -Z spatial scoring.

ZScore is the result of mapping a raw −Z value onto the shard ring and
scoring its proximity to the Lambert-W fixed point x* ≈ −0.5671.

## API

- `class ZScore` — Active -Z scoring result.
- `def compute_z_score` — Compute active -Z score and map it onto the shard ring.

## Internal imports

`sims.attractors`, `workers.cairrn._constants`, `workers.cairrn.formulas`

---

## Semantic links

→ [[2026-07-16-011935-cairrn-cairrn-worker-system]]
→ [[MATH]]
→ [[CODE]]
→ [[CODE]]
→ [[sims]]

## Related notes

→ [[source/workers-cairrn-worker]]
→ [[source/workers-cairrn-constants]]
→ [[source/workers-cairrn-formulas]]
→ [[source/workers-cairrn-layers]]
→ [[source/workers-cairrn-init]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[workers-index]]
→ [[workers-cairrn-layers]]
→ [[workers-cairrn-worker]]
→ [[workers-cairrn-formulas]]
→ [[workers-cairrn-desktop]]
→ [[workers-base]]

---

## Semantic links

→ [[workers-cairrn-worker]]
→ [[workers-cairrn-init]]
→ [[pipeline-worker-init]]
→ [[workers-cairrn-z-space]]
→ [[workers-base]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-worker-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-constants-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-mycelial-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-desktop-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
