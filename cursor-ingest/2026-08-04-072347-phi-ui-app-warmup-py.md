# phi / ui / _app / _warmup.py

#source #python

> path: phi/ui/_app/_warmup.py  
> ext: .py  

---

# phi / ui / _app / _warmup.py

phi.ui._app._warmup — CAIRRN cache warm-up orchestrator mixin.

Runs at app startup immediately after _restore_session() and
floor.warm_from_history() complete.  All work executes on the main thread,
each step yielding to the Qt event loop between phases via _sched(0, ...).

Warm-up sequence
----------------
Step 1  CAIRRN floor   — floor.root_pulse() for every page hub
Step 2  library cache  — LibraryPage.on_refresh() → full _rebuild()
Step 3  genre graph    — GenreRoom.on_refresh()   → build_tree() + layout
Step 4  playlist cache — PlaylistRoom.on_refresh() → path scan + filter

After step 4

Defines: _WarmupMixin, _start_warmup, _warm_cairrn, _warm_library, _warm_genre, _warm_playlist

---

## Semantic links

→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]
→ [[engine-hot-loader]]
→ [[engine-cairrn-scheduler]]
→ [[scripts-pretrain-loop]]
→ [[engine-phi-player]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-core-poll-cairrn-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-app-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-poll-engine-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-main-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-sleep-timer-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
