# source / engine-cairrn-dispatch.md

#doc #md

> path: source/engine-cairrn-dispatch.md  
> ext: .md  

---

# engine/cairrn_dispatch

#code #module #engine #code

> source_path: engine/cairrn_dispatch.py  
> package: engine  
> module: engine/cairrn_dispatch  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/cairrn_dispatch`  
**Source:** `engine/cairrn_dispatch.py`

CAIRRNDispatcher — central CAIRRN-bound action dispatcher for all phi operations.

Architecture
------------
Every phi operation is a PhiAction that enters a priority queue.
The dispatcher owns the coherence gate.  On each step():

    coherence = exp(−steps_since_tick / τ)

    GATE CLOSED (coherence < 0.5671)          GATE OPEN (coherence ≥ 0.5671)
         │                                           │
         ▼                                           ▼
    prefeed(head)                           dequeue by priority
    compute result silently                 execute → may use prefeed
    queue unchanged                         CAIRRN CODE pipeline fires
    steps_since_tick += 1                   steps_since_tick = 0

Prefeedable actions (computed silently while gate builds):
    CLIP        → GeminiClipper runs in background; result cached
    SHUFFLE_NEXT → PrefeedShuffle.prefeed() stages next order

All other actions execute only at gate-open time — no prefeed.

Priority system
---------------
    priority < 0  : urgent  — sorted to front of queue
    priority = 0  : normal  — FIFO within the 0-band
    priority > 0  : deferred — sorted behind normal items

This is the CAIRRN control plane.  All button presses go here.

    Action kinds
    ------------
    CLIP          — query → tracks via GeminiClipper
    SHUFFLE_NEXT  — advance the prefeed shuffle cursor
    SHUFFLE_SEED  — bootstrap / force-commit the shuffle
    HUB_INJECT    — inject activation into a named station hub
    SHARD_INJECT  — inject activation into a specific shard index
    PROPAGATE     — run N harmonic propagation steps
    CAIRRN_RUN    — full 4-layer CAIRRN pipeline for one hub
    TEMPORAL_RE

---

## Semantic links

→ [[engine-cairrn-dispatch]]
→ [[mcp-server-tools-phi-dispatch]]
→ [[engine-cairrn-scheduler]]
→ [[engine-cairrn-bridge]]
→ [[workers-cairrn-formulas]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-scheduler-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-tracer-daemon-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-index-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
