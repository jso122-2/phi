# source / pipeline-bridge-mmap-pipe.md

#doc #md

> path: source/pipeline-bridge-mmap-pipe.md  
> ext: .md  

---

# pipeline/bridge/mmap_pipe

#code #module #pipeline #code

> source_path: pipeline/bridge/mmap_pipe.py  
> package: pipeline  
> module: pipeline/bridge/mmap_pipe  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/bridge/mmap_pipe`  
**Source:** `pipeline/bridge/mmap_pipe.py`

pipeline.bridge.mmap_pipe — anonymous mmap ring buffer.

Binary layout
-------------
    [0  : 24]  header : write_pos (int64) | read_pos (int64) | capacity (int64)
    [24 : ...]  slots  : capacity × slot_size bytes

Each slot:
    [0:2]  length prefix (uint16, big-endian) — number of payload bytes
    [2:slot_size]  payload (null-padded to slot_size-2 bytes)

Concurrency
-----------
A single threading.Condition serialises all put/get calls.  Both sides
block on the Condition when the buffer is full (put) or empty (get), and
notify_all() after every state change so waiters re-check the predicate.

Usage
-----
    pipe = MmapPipe(capacity=256)
    pipe.put(b"hello")           # blocks if full
    data = pipe.get(timeout=5.0) # None on timeout
    pipe.close()

## API

- `class MmapPipe` — Anonymous mmap ring buffer for inter-thread message passing.

---

## Semantic links

→ [[CODE]]
→ [[CODE]]
→ [[README]]
→ [[environment]]
→ [[environment]]

## Related notes

→ [[source/pipeline-bridge-init]]
→ [[source/pipeline-bridge-coordinator]]
→ [[source/pipeline-worker-init]]
→ [[source/engine-arm-injector]]
→ [[source/pipeline-utils-config]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[pipeline-bridge-init]]
→ [[pipeline-worker-init]]
→ [[pipeline-index]]
→ [[pipeline-fetcher-init]]
→ [[index]]
→ [[pipeline-sources-base]]

---

## Semantic links

→ [[pipeline-bridge-mmap-pipe]]
→ [[pipeline-bridge-init]]
→ [[pipeline-worker-init]]
→ [[engine-bridge-factory]]
→ [[pipeline-bridge-coordinator]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-bridge-init-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-bridge-mmap-pipe-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-init-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-bridge-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-init-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
