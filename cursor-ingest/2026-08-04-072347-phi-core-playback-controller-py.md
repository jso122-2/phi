# phi / core / playback_controller.py

#source #python

> path: phi/core/playback_controller.py  
> ext: .py  

---

# phi / core / playback_controller.py

phi.core.playback_controller — track-level playback state machine.

Owns the three operations that move the player from one track to another:
- ``load_and_play``  — load file into pygame and start playing.
- ``advance``        — end-of-track logic (repeat, ranker, queue advance).
- ``record_departure`` — stats / ELO / scrobble for the track being left.

UI side-effects (NowPlaying update, picker widget) are inverted as callbacks so
this class stays import-free from any UI framework.


Defines: PlaybackController, __init__, load_and_play, advance, record_departure, _record_departure_inner, play_path_direct, peek_next_path, handoff_after_crossfade

---

## Semantic links

→ [[engine-phi-player]]
→ [[PLAYBACK]]
→ [[scripts-embed-tracks]]
→ [[2026-07-16T19-50-20Z-phi floating UI + ASCII waveform — Layer 5 implementation]]
→ [[mcp-server-tools-phi-dispatch]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-phi-player-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-app-transport-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-queue-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-phi-player-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-playlist-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
