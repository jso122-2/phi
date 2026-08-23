# pipeline / worker / executor.py

#source #python

> path: pipeline/worker/executor.py  
> ext: .py  

---

# pipeline / worker / executor.py

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


Defines: TrackResult, JobResult, WorkerSummary, _process_job, run_workers, n_ok, n_failed, total_ok, total_failed

---

## Semantic links

→ [[pipeline-worker-executor]]
→ [[pipeline-worker-multi-source]]
→ [[pipeline-sources-base]]
→ [[pipeline-worker-init]]
→ [[worker]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-executor-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-worker-init-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-base-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-worker-multi-source-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-bridge-coordinator-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
