# pipeline / sources / base.py

#source #python

> path: pipeline/sources/base.py  
> ext: .py  

---

# pipeline / sources / base.py

pipeline.sources.base — abstract base for all download sources.

Every concrete source must implement download() and set a unique name.
Results carry enough context for the executor to log and retry.


Defines: DownloadResult, Source, download

---

## Semantic links

→ [[pipeline-sources-base]]
→ [[pipeline-worker-executor]]
→ [[pipeline-worker-multi-source]]
→ [[pipeline-fetcher-models]]
→ [[pipeline-worker-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-base-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-worker-executor-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-executor-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-worker-init-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-fetcher-models-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
