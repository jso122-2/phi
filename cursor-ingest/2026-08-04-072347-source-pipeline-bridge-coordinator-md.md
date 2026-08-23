# source / pipeline-bridge-coordinator.md

#doc #md

> path: source/pipeline-bridge-coordinator.md  
> ext: .md  

---

# pipeline/bridge/coordinator

#code #module #pipeline #code

> source_path: pipeline/bridge/coordinator.py  
> package: pipeline  
> module: pipeline/bridge/coordinator  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/bridge/coordinator`  
**Source:** `pipeline/bridge/coordinator.py`

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
        Coordinator.complete_thread reads {job_id, ok, path?} records,
        calls the on_complete callback, and increments the done counter.
        When done == total, the done_event is set.

Usage
-----
    from pipeline.bridge.mmap_pipe import MmapPipe
    from pipeline.bridge.coordinator import Coordinator

    dispatch = MmapPipe(capacity=64)
    complete = MmapPipe(capacity=64)

    def on_done(job_id: str, ok: bool, path: str | None) -> None:
        print(f"{job_id}: {'ok' if ok else 'FAIL'} → {path}")

    coord = Coordinator(jobs, dispatch_pipe=dispatch, complete_pipe=complete,
                        on_complete=on_done)
    coord.start()

    # Workers consume dispatch_pipe and write to complete_pipe independently.
    # When all completions arrive:
    coord.wait(timeout=3600)
    coord.stop()

Wire workers with the companion PipeWorker in this module:

    workers = [PipeWorker(dispatch, complete, coord.job_map, sources, proxy)
               for _ in range(n_threads)]
    for w in workers: w.start()
    coord.wait()
    coord.stop()
    for w in workers: w.stop(); w.join()

Sentinel protocol
-----

---

## Semantic links

→ [[pipeline-bridge-coordinator]]
→ [[pipeline-bridge-init]]
→ [[pipeline-worker-init]]
→ [[pipeline-worker-executor]]
→ [[workers-cairrn-worker]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-bridge-init-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-bridge-coordinator-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-bridge-mmap-pipe-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
