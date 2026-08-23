# workers / cairrn / worker.py

#source #python

> path: workers/cairrn/worker.py  
> ext: .py  

---

# workers / cairrn / worker.py


CAIRRN worker classes — CAIRRNWorker, CAIRRNBatch, and supporting utilities.

CAIRRNWorker wraps any callable and runs it through the three-layer pipeline
(plus optional active -Z scoring when Z-space inputs are provided).
CAIRRNBatch spins one worker per hub and runs them simultaneously.


Defines: CAIRRNResult, CAIRRNWorker, CAIRRNBatch, _extract_metric, spawn_hub_worker, _build_static_shard_map, to_dict, __init__, _run, cairrn_log, shard_summary, __repr__, __init__, run_all, summary, coherence_map

---

## Semantic links

→ [[workers-cairrn-worker]]
→ [[workers-base]]
→ [[workers-cairrn-layers]]
→ [[workers-cairrn-z-space]]
→ [[workers-cairrn-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-worker-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-layers-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-base-md]]
→ [[cursor-ingest/2026-08-04-072347-workers-base-py]]
→ [[cursor-ingest/2026-08-04-072347-workers-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
