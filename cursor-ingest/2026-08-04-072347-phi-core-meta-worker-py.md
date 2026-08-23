# phi / core / meta_worker.py

#source #python

> path: phi/core/meta_worker.py  
> ext: .py  

---

# phi / core / meta_worker.py

phi.core.meta_worker — background metadata loading and model annotation.

Owns two responsibilities:
- Single-track async meta (read tag → store → fire on_meta_ready callback)
- Batch background prime (bulk SQL read → store → schedule model annotation run)

All UI side-effects are inverted via callbacks so this module stays import-clean
from UI code.


Defines: MetaWorker, __init__, async_meta, _async_meta_worker, fetch_duration, _duration_loop, _fetch_duration_worker, bg_meta, _bg_meta_sync, schedule_model_run, _done

---

## Semantic links

→ [[workers-base]]
→ [[workers-cairrn-worker]]
→ [[workers]]
→ [[workers]]
→ [[pipeline-bridge-coordinator]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-app-workers-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-app-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-track-helpers-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-registry-py]]
→ [[cursor-ingest/2026-08-04-072347-workers-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
