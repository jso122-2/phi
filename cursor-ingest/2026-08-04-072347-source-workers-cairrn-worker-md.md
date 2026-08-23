# source / workers-cairrn-worker.md

#doc #md

> path: source/workers-cairrn-worker.md  
> ext: .md  

---

# workers/cairrn/worker

#code #module #workers #code

> source_path: workers/cairrn/worker.py  
> package: workers  
> module: workers/cairrn/worker  
> hub: CODE  
> created_ts:   

---

**Package:** `workers`  
**Module:** `workers/cairrn/worker`  
**Source:** `workers/cairrn/worker.py`

CAIRRN worker classes — CAIRRNWorker, CAIRRNBatch, and supporting utilities.

CAIRRNWorker wraps any callable and runs it through the three-layer pipeline
(plus optional active -Z scoring when Z-space inputs are provided).
CAIRRNBatch spins one worker per hub and runs them simultaneously.

## API

- `class CAIRRNResult` — Full three-layer processing result attached to every CAIRRNWorker run.
- `class CAIRRNWorker` — A Worker anchored to a CAIRRN station hub.
- `class CAIRRNBatch` — Spin up one CAIRRNWorker per CAIRRN hub and run them all.
- `def _extract_metric` — Best-effort extraction of a float metric from a worker return value.
- `def spawn_hub_worker` — Convenience factory: create a CAIRRNWorker anchored to hub_name.
- `def _build_static_shard_map`

## Internal imports

`sims.attractors`, `sims.ana_chi`, `workers.base`, `workers.cairrn._constants`, `workers.cairrn.layers`, `workers.cairrn.desktop`, `workers.cairrn.z_space`, `workers.cairrn`

---

## Semantic links

→ [[2026-07-16-011935-cairrn-cairrn-worker-system]]
→ [[workers]]
→ [[workers]]
→ [[cairrn]]
→ [[worker]]

## Related notes

→ [[source/workers-base]]
→ [[source/workers-cairrn-layers]]
→ [[source/pipeline-bridge-coordinator]]
→ [[source/workers-cairrn-init]]
→ [[source/pipeline-worker-init]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[workers-cairrn-z-space]]
→ [[workers-index]]
→ [[workers-base]]
→ [[workers-cairrn-layers]]
→ [[pipeline-worker-init]]
→ [[mcp-server-tools-cairrn]]

---

## Semantic links

→ [[workers-cairrn-worker]]
→ [[workers-cairrn-init]]
→ [[workers-base]]
→ [[pipeline-worker-init]]
→ [[workers-index]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-z-space-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-constants-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-mycelial-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-desktop-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
