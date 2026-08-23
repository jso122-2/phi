# phi / ui / qt / rooms / playlist_room.py

#source #python

> path: phi/ui/qt/rooms/playlist_room.py  
> ext: .py  

---

# phi / ui / qt / rooms / playlist_room.py

phi.ui.qt.rooms.playlist_room — Qt drag-and-build playlist studio.

Replaces phi.ui.rooms.playlist_room.PlaylistRoom (tk.Frame).

Two-pane layout:
  Left  — library browser (filterable track list)
  Right — working playlist (reorderable, save as M3U)

Room protocol: on_show(), on_refresh(), sync_transport()


Defines: PlaylistRoom, __init__, _build, on_show, on_refresh, sync_transport, mark_playing, _reload_library, _apply_filter, _on_src_double, _on_remove, _on_clear, _on_play, _on_save, _on_load

---

## Semantic links

→ [[engine-phi-player]]
→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]
→ [[scripts-embed-tracks]]
→ [[2026-07-16T19-50-20Z-phi floating UI + ASCII waveform — Layer 5 implementation]]
→ [[PLAYBACK]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-playlist-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-genre-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-library-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-mixer-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
