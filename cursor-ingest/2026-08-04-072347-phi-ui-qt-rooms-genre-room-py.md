# phi / ui / qt / rooms / genre_room.py

#source #python

> path: phi/ui/qt/rooms/genre_room.py  
> ext: .py  

---

# phi / ui / qt / rooms / genre_room.py

phi.ui.qt.rooms.genre_room — Qt full-page genre graph room.

Replaces phi.ui.rooms.genre_room.GenreRoom (tk.Frame).

Layout
------
┌──────────────────────────────────────────────────────┐
│  genre graph / fractal zoom  (GenreGraphView)        │
│  ASCII network — zoom into genres → subgenres → tracks│
├──────────────────────────────────────────────────────┤
│  mini transport                                       │
└──────────────────────────────────────────────────────┘

Room protocol: on_show(), on_refresh(), sync_transport(), mark_playing()


Defines: GenreRoom, __init__, _build, on_show, on_refresh, refresh, sync_transport, update_transport, mark_playing, set_playing

---

## Semantic links

→ [[models-genre-predictor]]
→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]
→ [[graph-hub-classifier]]
→ [[engine-phi-player]]
→ [[engine-phi-session]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-genre-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-library-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-mixer-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-playlist-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-genre-graph-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
