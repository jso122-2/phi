# source / engine-cursor-tracer.md

#doc #md

> path: source/engine-cursor-tracer.md  
> ext: .md  

---

# engine/cursor_tracer

#code #module #engine #code

> source_path: engine/cursor_tracer.py  
> package: engine  
> module: engine/cursor_tracer  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/cursor_tracer`  
**Source:** `engine/cursor_tracer.py`

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
Euclidean distance from screen centre, normalised to [0, 1] by half-diagonal.
Cursor at centre → metric ≈ 0.0 (stable)
Cursor at corner → metric ≈ 1.0 (maximal activity)

CAIRRN Scheduler intervals
--------------------------
coherence ≥ 0.80  → slow lane  2000 ms  (system coherent, low urgency)
coherence  < 0.50  → fast lane   200 ms  (system in flux, track closely)
else               → base rate   500 ms

Hub routing
-----------
CODE hub (shards 3–4): cursor activity = code navigation pressure.
If CAIRRN re-routes to HOME (incoherent), that is recorded in the sample.

Usage
-----
    tracer = CursorTracer(max_samples=200)
    tracer.start()          # daemon thread — dies with process
    ...
    snap = tracer.snapshot()   # thread-safe dict summary
    tracer.stop()

## API

- `def _get_cursor_pos` — Return (x, y) in screen pixels. Returns (0, 0) when Quartz is absent.
- `def _cursor_metric` — Normalise screen position to a single float in [0, 1].
- `class HoverRegion` — Named rectangular screen region that triggers a CAIRRN hover prefetch.
- `class CursorSample` — One cursor observation after CAIRRN pipeline processing.
- `class CAIRRNScheduler` — Maps CAIRR

---

## Semantic links

→ [[engine-cursor-tracer]]
→ [[tools-cursor-ingest]]
→ [[engine-tracer-daemon]]
→ [[scripts-spawn-tracer]]
→ [[engine-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-tools-cursor-ingest-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-cursor-tracer-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cursor-tracer-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-cairrn-tracer-daemon-md]]
→ [[cursor-ingest/2026-08-04-072347-tools-cursor-ingest-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
