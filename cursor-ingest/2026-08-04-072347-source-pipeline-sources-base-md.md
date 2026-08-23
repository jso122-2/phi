# source / pipeline-sources-base.md

#doc #md

> path: source/pipeline-sources-base.md  
> ext: .md  

---

# pipeline/sources/base

#code #module #pipeline #code

> source_path: pipeline/sources/base.py  
> package: pipeline  
> module: pipeline/sources/base  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/sources/base`  
**Source:** `pipeline/sources/base.py`

pipeline.sources.base — abstract base for all download sources.

Every concrete source must implement download() and set a unique name.
Results carry enough context for the executor to log and retry.

## API

- `class DownloadResult`
- `class Source` — Abstract download source.

## Internal imports

`pipeline.fetcher.models`

---

## Semantic links

→ [[index]]
→ [[worker]]
→ [[fetcher]]
→ [[2025-02-20-075321-docker-and-celery-commands]]
→ [[2025-05-20-052550-operator-scraping-prompts]]

## Related notes

→ [[source/pipeline-worker-executor]]
→ [[source/pipeline-worker-init]]
→ [[source/pipeline-worker-multi-source]]
→ [[source/pipeline-fetcher-models]]
→ [[source/pipeline-fetcher-init]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[pipeline-worker-init]]
→ [[pipeline-fetcher-init]]
→ [[pipeline-worker-multi-source]]
→ [[pipeline-index]]
→ [[pipeline-bridge-init]]
→ [[pipeline-fetcher-models]]

---

## Semantic links

→ [[pipeline-sources-base]]
→ [[pipeline-worker-multi-source]]
→ [[pipeline-fetcher-models]]
→ [[pipeline-sources-internet-archive]]
→ [[pipeline-fetcher-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-base-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-internet-archive-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-fetcher-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-multi-source-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
