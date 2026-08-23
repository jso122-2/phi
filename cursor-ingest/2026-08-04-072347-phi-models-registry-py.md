# phi / models / registry.py

#source #python

> path: phi/models/registry.py  
> ext: .py  

---

# phi / models / registry.py

phi.models.registry — model registration and background batch runner.

Usage
-----
    registry = ModelRegistry()
    registry.register(BPMModel())
    registry.register(KeyModel())

    # Run all models on a batch of tracks (background thread)
    registry.run_batch(paths, library, on_progress=cb, on_done=cb)


Defines: ModelRegistry, __init__, register, models, running, run_batch, run_single, status, _worker

---

## Semantic links

→ [[scripts-pretrain-loop]]
→ [[scripts-train-d4]]
→ [[engine-phi-session]]
→ [[pipeline-worker-executor]]
→ [[pipeline-fetcher-models]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-core-meta-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-app-workers-py]]
→ [[cursor-ingest/2026-08-04-072347-scripts-train-d4-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-batch-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-utils-perpetual-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
