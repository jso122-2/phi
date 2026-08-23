# phi / core / _poll_xfade.py

#source #python

> path: phi/core/_poll_xfade.py  
> ext: .py  

---

# phi / core / _poll_xfade.py

phi.core._poll_xfade — crossfade state machine and gapless preload tick.

Crossfade and gapless are mutually exclusive (gapless only runs when
``CROSSFADE_SECS == 0``), so they live in the same handler.


Defines: XfadeGaplessTick, __init__, xfade_handled, reset_gapless, tick, _tick_crossfade, _tick_gapless

---

## Semantic links

→ [[engine-cairrn-dispatch]]
→ [[engine-hot-loader]]
→ [[engine-cairrn-scheduler]]
→ [[engine-gate]]
→ [[engine-phi-player]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-core-poll-engine-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-poll-state-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-race-watcher-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-watchdog-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-dispatch-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
