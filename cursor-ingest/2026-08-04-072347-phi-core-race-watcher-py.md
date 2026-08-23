# phi / core / race_watcher.py

#source #python

> path: phi/core/race_watcher.py  
> ext: .py  

---

# phi / core / race_watcher.py

phi.core.race_watcher — Pericles-pattern playback race condition watchdog.

Mirrors the PericlesWatchdog in spawn_tracer.py, adapted for phi's
real-time poll loop rather than batch cycles.

Five race conditions monitored
──────────────────────────────
    DOUBLE_PLAY       channel-0 busy while _xfading is False
                      → channel-0 was not stopped after a crossfade completed
                      → escalation: abort_crossfade() to silence rogue channel

    XFADE_HANG        _xfading True for longer than 2× CROSSFADE_SECS
                      → crossfade tick loop hung or never c

Defines: PhiRaceWatcher, __init__, attach_dr_watchdog, poll_tick, on_load_and_play, on_advance, on_gapless_queue, status_line

---

## Semantic links

→ [[engine-phi-player]]
→ [[engine-hot-loader]]
→ [[engine-cairrn-scheduler]]
→ [[engine-tracer-daemon]]
→ [[engine-phi-session]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-watchdog-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-poll-engine-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-enrich-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-watcher-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-lastfm-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
