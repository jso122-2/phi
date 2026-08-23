# pipeline / bridge / mmap_pipe.py

#source #python

> path: pipeline/bridge/mmap_pipe.py  
> ext: .py  

---

# pipeline / bridge / mmap_pipe.py


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
notify_all() after every state change so waiters re-check the predi

Defines: MmapPipe, __init__, _read_header, _write_header, _slot_offset, put, get, qsize, __len__, close, __repr__

---

## Semantic links

→ [[pipeline-bridge-mmap-pipe]]
→ [[pipeline-bridge-init]]
→ [[pipeline-bridge-coordinator]]
→ [[engine-bridge-factory]]
→ [[engine-arm-injector]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-pipeline-bridge-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-bridge-mmap-pipe-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-pipeline-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-bridge-init-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-bridge-coordinator-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
