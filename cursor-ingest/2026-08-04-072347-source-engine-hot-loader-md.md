# source / engine-hot-loader.md

#doc #md

> path: source/engine-hot-loader.md  
> ext: .md  

---

# engine/hot_loader

#code #module #engine #code

> source_path: engine/hot_loader.py  
> package: engine  
> module: engine/hot_loader  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/hot_loader`  
**Source:** `engine/hot_loader.py`

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
   next.  Register with a signal_fn derived from hub activation thresholds:

       hot_loader.register(
           name="track:/path/T0.npy",
           signal_fn=lambda: code_activation() > 0.7,
           load_fn=lambda: np.load("/path/T0.npy"),
       )

   The load fires automatically when CODE hub heats up — before the shuffle
   cursor reaches that track.

2. Manual signal (hover / explicit prefetch)
   The UI calls signal() when the user hovers a button.  The hot loader
   fires the load_fn immediately on the next step():

       # At app start — register all button actions
       hot_loader.register("hover:next_track", signal_fn=lambda: False, load_fn=compute_next)

       # When hover event fires
       hot_loader.signal("hover:next_track")

       # By the time the click arrives the result is cached
       result = hot_loader.get("hover:next_track")  # instant

Lifecycle
---------
    step() → for each entry: if (pending or signal fires) and not loaded/loading
                 → spawn daemon thread running load_fn
                 → _loading=True until thread completes
                 → _loaded=True + _result set on completion

---

## Semantic links

→ [[engine-hot-loader]]
→ [[engine-index]]
→ [[engine-cairrn-dispatch]]
→ [[engine-phi-session]]
→ [[engine-cairrn-scheduler]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-hot-loader-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-hot-loader-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-phi-dispatch-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-dispatch-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
