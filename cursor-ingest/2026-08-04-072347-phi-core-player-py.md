# phi / core / player.py

#source #python

> path: phi/core/player.py  
> ext: .py  

---

# phi / core / player.py

phi.core.player — AVFoundation AVPlayer audio engine.

PlayerEngine owns all playback state.  The public API is identical to the
former python-mpv/libmpv implementation so PollEngine, PlaybackController,
and all callers are unchanged.

Why AVPlayer instead of libmpv
──────────────────────────────
On macOS 26 (Tahoe), libmpv's mpv_create() raises a fatal SIGBUS inside
CoreMedia initialisation.  The mpv binary also crashes.  AVPlayer is the
native macOS audio/video engine and works without issues on any macOS version.

Requires a running event loop on the main thread.  AVPlayer property reads
(c

Defines: _ensure_av, _cm, _secs, register_qt_dispatch, _dispatch_main, _AVChannel, PlayerEngine, __init__, load, play, _play_when_ready, pause, stop, seek, set_volume, position, rate, rate_and_position, duration, eof_reached, has_item, terminate, __init__, load, play, pause, unpause, stop, seek, _apply_volume, set_volume, set_muted, muted, position, raw_ms, is_busy, tick_state, paused, loaded_path, xfade_channel_busy

---

## Semantic links

→ [[engine-phi-player]]
→ [[scripts-embed-tracks]]
→ [[PLAYBACK]]
→ [[environment]]
→ [[environment]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-phi-player-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-audio-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-audio-media-keys-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-phi-player-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-playback-controller-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
