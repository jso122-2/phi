# phi / ui / _app / _track_ui.py

#source #python

> path: phi/ui/_app/_track_ui.py  
> ext: .py  

---

# phi / ui / _app / _track_ui.py

phi.ui._app._track_ui — apply track to UI surfaces + playback helpers.

CAIRRN scheduling
-----------------
Every track transition is routed through the ForestFloor (TRACK_TRANSITION →
CODE hub) before any UI surface is updated.

Operation priority tiers:
    IMMEDIATE  — transport controls, beat reset, waveform load (no gate)
    PREFEED    — ASCII art grid (PIL is expensive; computed off-thread)
    COHERENT   — sidebar, info drawer, lyrics load (coherent → now, else +250 ms)
    ALWAYS     — notification, mini player, Last.fm, media keys, vault query
                 (user-facing signals th

Defines: _TrackUIMixin, _apply_track_to_ui, _preload_art_for_path, _load_and_play, _advance, _record_track_departure, _play_path_direct, _peek_next_path, _open_picker, on_toggle_ranker, on_toggle_picker, _update_coherent_surfaces

---

## Semantic links

→ [[engine-phi-player]]
→ [[engine-cairrn-dispatch]]
→ [[engine-cairrn-scheduler]]
→ [[cairrn]]
→ [[mcp-server-tools-phi-dispatch]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-core-ranker-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-curve-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-types-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-playback-controller-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-phi-player-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
