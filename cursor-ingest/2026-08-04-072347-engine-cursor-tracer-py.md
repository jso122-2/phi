# engine / cursor_tracer.py

#source #python

> path: engine/cursor_tracer.py  
> ext: .py  

---

# engine / cursor_tracer.py


cursor_tracer.py — Mouse cursor movement tracer with CAIRRN scheduling.

Architecture
------------
CursorSample      — one timestamped (x, y, metric, hub, coherence) snapshot
CAIRRNScheduler   — derives next sample interval from CAIRRN coherence output
CursorTracer      — daemon thread: sample OS cursor → metric → CAIRRN → store

OS cursor source
----------------
Quartz.CoreGraphics on macOS (zero extra deps — system framework).
Falls back to (0, 0) if unavailable so the tracer still runs in tests.

Metric encoding
---------------
Euclidean distance from screen centre, normalised to [0, 1] by

Defines: _get_cursor_pos, _cursor_metric, HoverRegion, CursorSample, CAIRRNScheduler, CursorTracer, contains, as_dict, __init__, update, interval_ms, interval_s, __init__, register_hover, attach_dispatcher, _check_hover, start, stop, _loop, _tick, snapshot, samples, scheduler, __repr__

---

## Semantic links

→ [[engine-cursor-tracer]]
→ [[engine-cairrn-tracer-daemon]]
→ [[engine-tracer-daemon]]
→ [[engine-cairrn-scheduler]]
→ [[tools-cursor-ingest]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-cursor-tracer-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-tracer-daemon-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-tracer-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-watchdog-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-cairrn-scheduler-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
