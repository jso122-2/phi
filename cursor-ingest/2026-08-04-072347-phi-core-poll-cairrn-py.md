# phi / core / _poll_cairrn.py

#source #python

> path: phi/core/_poll_cairrn.py  
> ext: .py  

---

# phi / core / _poll_cairrn.py

phi.core._poll_cairrn — CAIRRN heartbeat + dispatcher step, off the main thread.

Both ``floor.heartbeat()`` and ``dispatcher.step()`` can be slow (neural inference,
CAIRRN routing, mycelial tick).  Neither must run on the Qt main thread.
A single daemon thread handles them sequentially so heartbeat always precedes step.
The ``_running`` flag prevents a backlog when a tick takes longer than the cadence.


Defines: CairnTick, __init__, tick, _do

---

## Semantic links

→ [[engine-cairrn-dispatch]]
→ [[engine-cairrn-scheduler]]
→ [[engine-hot-loader]]
→ [[cairrn]]
→ [[engine-cairrn-tracer-daemon]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-core-poll-engine-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-app-warmup-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-app-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-dispatch-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-watchdog-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
