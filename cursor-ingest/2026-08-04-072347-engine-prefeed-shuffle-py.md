# engine / prefeed_shuffle.py

#source #python

> path: engine/prefeed_shuffle.py  
> ext: .py  

---

# engine / prefeed_shuffle.py


CAIRRN-bound prefeed shuffle — double-buffer soft-queue for track ordering.

Architecture (Instagram analogy)
---------------------------------
Instagram pre-uploads a photo to its CDN while you're still editing it.
When you press "Share", the upload is already done — zero visible latency.

This module does the same for shuffle order:

    COHERENCE BUILDING          COHERENCE THRESHOLD CROSSED
    (gate closed)               (gate opens)
         │                              │
         ▼                              ▼
    prefeed()                      commit()
    compute next order      

Defines: _build_Q, _harmonic_scores, _shuffle_order, ShufflePeek, ShuffleStepResult, PrefeedShuffle, CAIRRNPrefeedShuffle, make_prefeed_shuffle, n, as_dict, __init__, prefeed, commit, next, peek, has_active, has_pending, active_len, pending_len, cursor, __repr__, __init__, seed, step, next, peek_active, peek_and_preload, coherence, gate_open, steps_since_commit, ticks_run, shuffle, state, _read_code_activation, __repr__

---

## Semantic links

→ [[engine-prefeed-shuffle]]
→ [[mcp-server-tools-prefeed-shuffle]]
→ [[engine-phi-player]]
→ [[pipeline-worker-executor]]
→ [[pipeline-sources-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-prefeed-shuffle-md]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-prefeed-shuffle-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-prefeed-shuffle-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-phi-player-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-utils-replay-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
