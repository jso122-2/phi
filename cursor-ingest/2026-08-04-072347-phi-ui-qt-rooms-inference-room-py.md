# phi / ui / qt / rooms / inference_room.py

#source #python

> path: phi/ui/qt/rooms/inference_room.py  
> ext: .py  

---

# phi / ui / qt / rooms / inference_room.py

phi.ui.qt.rooms.inference_room — ML Inference room.

Runs SongDerivativeModel.score_library() in a background QThread and
displays the ranked D1–D4 score table for every track in the library.

Layout
------
┌──────────────────────────────────────────────────────────────────────┐
│  INFERENCE        ‹ Dragon · Inference · Forge ›         [Run Scores]│
├───────────────────────────────────────┬──────────────────────────────┤
│  D4  D3  D1  D2  title / artist       │  SELECTED TRACK              │
│  ████▒░░  ████▒░░  …                  │  D4  ████████▒░░ 0.842        │
│  (playing row highlighted

Defines: _ScoreWorker, _Bar, _DetailPanel, _score_block, MLInferencePage, __init__, run, __init__, set_frac, paintEvent, __init__, _sep, _bar_row, _build, _kv, show_track, clear, __init__, _build, _make_header, _make_route_label, _on_nav_prev, _on_nav_next, _on_run, _on_scores_ready, _on_score_error, _on_selection, _populate_list, _highlight_playing, _library_paths, _set_status, on_show, on_refresh, refresh, sync_transport, update_transport, mark_playing, set_playing

---

## Semantic links

→ [[models-genre-predictor]]
→ [[engine-phi-player]]
→ [[scripts-embed-tracks]]
→ [[scripts-train-d4]]
→ [[PLAYBACK]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-models-song-derivative-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-dragon-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-derivative-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-dragon-panel-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-bpm-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
