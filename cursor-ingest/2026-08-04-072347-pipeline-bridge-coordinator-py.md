# pipeline / bridge / coordinator.py

#source #python

> path: pipeline/bridge/coordinator.py  
> ext: .py  

---

# pipeline / bridge / coordinator.py


pipeline.bridge.coordinator — dispatch + complete daemon threads.

Architecture
------------
Two daemon threads bridge a job deque and a worker pool via two MmapPipe
instances:

    dispatch_pipe  (Coordinator → Workers)
        Coordinator.dispatch_thread pops pending Jobs from the internal deque,
        serialises {job_id} as JSON, and writes to dispatch_pipe.
        Workers read job IDs, look them up in the shared job_map, download,
        then write a completion record to complete_pipe.

    complete_pipe  (Workers → Coordinator)
        Coordinator.complete_thread reads {job_id, ok, p

Defines: Coordinator, PipeWorker, __init__, start, stop, wait, n_done, _dispatch_loop, _complete_loop, __init__, run, stop, _process_job

---

## Semantic links

→ [[pipeline-bridge-coordinator]]
→ [[workers-cairrn-worker]]
→ [[pipeline-worker-executor]]
→ [[pipeline-worker-init]]
→ [[workers-base]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-bridge-coordinator-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-worker-init-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-worker-executor-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-bridge-init-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-pipeline-bridge-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
