# source / pipeline-worker-executor.md

#doc #md

> path: source/pipeline-worker-executor.md  
> ext: .md  

---

# pipeline/worker/executor

#code #module #pipeline #code

> source_path: pipeline/worker/executor.py  
> package: pipeline  
> module: pipeline/worker/executor  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/worker/executor`  
**Source:** `pipeline/worker/executor.py`

pipeline.worker.executor — parallel download thread pool.

Drains a list of Jobs using N threads.  Each thread calls
download_track() for every track in the job, trying sources in
priority order.

Multi-pass retry
----------------
Up to `retry_passes` retry rounds for failed tracks between passes.
Pass 1 failure → wait pass_delays_s[0] → pass 2
Pass 2 failure → wait pass_delays_s[1] → pass 3
...

Summary
-------
run_workers() returns a WorkerSummary with per-job counts of
ok/failed tracks and per-track DownloadResult objects.

## API

- `class TrackResult`
- `class JobResult`
- `class WorkerSummary`
- `def _process_job` — Process a single Job across all retry passes.  Called from thread pool.
- `def run_workers` — Run download jobs in parallel using a ThreadPoolExecutor.

## Internal imports

`pipeline.fetcher.models`, `pipeline.sources`, `pipeline.sources.base`, `pipeline.worker.multi_source`

---

## Semantic links

→ [[worker]]
→ [[queue]]
→ [[2025-09-09-102444-2025-09-09t20-25-19-520-10-00]]
→ [[2025-08-28-121214-2025-08-28t22-12-14-433-10-00]]
→ [[workers]]

## Related notes

→ [[source/pipeline-worker-multi-source]]
→ [[source/pipeline-sources-base]]
→ [[source/pipeline-worker-init]]
→ [[source/pipeline-bridge-coordinator]]
→ [[source/pipeline-worker-fs-organizer]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[pipeline-worker-init]]
→ [[pipeline-worker-multi-source]]
→ [[pipeline-sources-base]]
→ [[pipeline-index]]
→ [[pipeline-bridge-init]]
→ [[pipeline-fetcher-init]]

---

## Semantic links

→ [[pipeline-worker-executor]]
→ [[pipeline-worker-init]]
→ [[pipeline-sources-base]]
→ [[pipeline-worker-multi-source]]
→ [[pipeline-bridge-coordinator]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-pipeline-worker-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-init-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-worker-executor-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-multi-source-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-fetcher-init-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
