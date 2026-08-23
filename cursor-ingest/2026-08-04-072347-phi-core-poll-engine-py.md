# phi / core / poll_engine.py

#source #python

> path: phi/core/poll_engine.py  
> ext: .py  

---

# phi / core / poll_engine.py

phi.core.poll_engine — timer-driven playback polling orchestrator.

Runs at ``POLL_MS`` cadence on the Qt main thread.  Owns the crossfade,
gapless-preload, CAIRRN heartbeat, Now-Playing sync, and end-of-track detection
ticks.  All external state is injected; the engine holds no UI references.

Sub-tick handlers (one job each):
    BeatTick        — beat sim + visualiser energy   (_poll_beat)
    XfadeGaplessTick— crossfade + gapless preload    (_poll_xfade)
    MediaKeysTick   — rate-limited NowPlaying sync   (_poll_media_keys)
    CairnTick       — off-thread CAIRRN heartbeat    (_poll_cairr

Defines: PollEngine, __init__, start, _poll

---

## Semantic links

→ [[engine-phi-player]]
→ [[engine-cairrn-scheduler]]
→ [[engine-hot-loader]]
→ [[engine-cairrn-dispatch]]
→ [[PLAYBACK]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-core-poll-cairrn-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-poll-xfade-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-poll-beat-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-watchdog-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-poll-state-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
