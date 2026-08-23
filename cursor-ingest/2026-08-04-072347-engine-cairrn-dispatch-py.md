# engine / cairrn_dispatch.py

#source #python

> path: engine/cairrn_dispatch.py  
> ext: .py  

---

# engine / cairrn_dispatch.py


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
  

Defines: PhiActionKind, PhiAction, DispatchResult, DoubleRouteEvent, DoubleRouteWatchdog, CAIRRNDispatcher, make_dispatcher, as_dict, as_dict, as_dict, __init__, observe, state, observe_song_transition, clear, __init__, enqueue, step, force_dispatch, coherence, gate_open, queue_depth, ticks_run, steps_since_tick, queue_snapshot, history_snapshot, attach_forest_floor, attach_substrate, attach_player, attach_double_route_watchdog, attach_hot_loader, signal_hover, state, _prefeed, _prefeed_clip, _prefeed_shuffle_next, _prefeed_load_track, _prefeed_hover, _execute, _exec_clip

---

## Semantic links

→ [[engine-cairrn-dispatch]]
→ [[engine-cairrn-scheduler]]
→ [[mcp-server-tools-phi-dispatch]]
→ [[engine-gate]]
→ [[engine-cairrn-tracer-daemon]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-phi-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-scheduler-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-router-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-dispatch-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-stress-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
