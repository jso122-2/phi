# source / workers-base.md

#doc #md

> path: source/workers-base.md  
> ext: .md  

---

# workers/base

#code #module #workers #code

> source_path: workers/base.py  
> package: workers  
> module: workers/base  
> hub: CODE  
> created_ts:   

---

**Package:** `workers`  
**Module:** `workers/base`  
**Source:** `workers/base.py`

Base worker — unit of computation in the pipeline.

A Worker wraps a callable (sim function, data fetch, transform, etc.)
and runs it with consistent logging, error handling, and result storage.
Subclass and override `_run` to define new worker types.

## API

- `class Status`
- `class WorkerResult`
- `class Worker` — Base worker.
- `class SimWorker` — Worker that wraps a sims.* function and stores the trajectory.
- `class BatchWorker` — Run multiple Workers in sequence and collect results.

---

## Semantic links

→ [[workers]]
→ [[workers]]
→ [[worker]]
→ [[CODE]]
→ [[CODE]]

## Related notes

→ [[source/workers-cairrn-worker]]
→ [[source/pipeline-worker-init]]
→ [[source/pipeline-bridge-coordinator]]
→ [[source/workers-cairrn-layers]]
→ [[source/pipeline-worker-fs-organizer]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[pipeline-worker-init]]
→ [[workers-index]]
→ [[workers-cairrn-worker]]
→ [[workers-cairrn-z-space]]
→ [[index]]
→ [[workers-cairrn-layers]]

---

## Semantic links

→ [[workers-base]]
→ [[workers-cairrn-worker]]
→ [[workers]]
→ [[pipeline-worker-init]]
→ [[workers]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-workers-base-py]]
→ [[cursor-ingest/2026-08-04-072347-workers-md]]
→ [[cursor-ingest/2026-08-04-072347-workers-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-init-md]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-worker-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
