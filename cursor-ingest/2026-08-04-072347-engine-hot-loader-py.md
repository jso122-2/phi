# engine / hot_loader.py

#source #python

> path: engine/hot_loader.py  
> ext: .py  

---

# engine / hot_loader.py


CAIRRNHotLoader — speculative prefetch engine for phi operations.

Architecture
------------
Every phi action that could block (track load, clip query, hub compute) can be
registered with a signal function and a load function.  On each step() call the
hot loader checks all signals; when a signal fires it kicks off the load in a
background daemon thread so the result is in cache before the action is needed.

Two entry-point patterns
------------------------
1. Signal-driven (predictive)
   The scheduler knows the CAIRRN attractor basin and can predict what will fire
   next.  Register with a s

Defines: HotLoadMetrics, _HotEntry, HotLoadResult, CAIRRNHotLoader, total_lookups, hit_rate, miss_rate, avg_load_duration_s, avg_latency_saved_s, avg_lead_time_s, as_dict, __init__, peek, invalidate, load_duration_s, lead_time_s, _run, try_fire, state, as_dict, __init__, register, signal, register_and_signal, invalidate, invalidate_all, unregister, step, get, _peek, is_ready, metrics, reset_metrics, state, summary, _make_complete_cb, _evict_if_needed, __len__, __repr__, _cb

---

## Semantic links

→ [[engine-hot-loader]]
→ [[engine-cairrn-dispatch]]
→ [[mcp-server-tools-phi-dispatch]]
→ [[engine-cairrn-scheduler]]
→ [[engine-phi-player]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-hot-loader-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-hot-loader-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-phi-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-app-dispatch-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
