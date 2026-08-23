# phi / ui / qt / rooms / mixer_room.py

#source #python

> path: phi/ui/qt/rooms/mixer_room.py  
> ext: .py  

---

# phi / ui / qt / rooms / mixer_room.py

phi.ui.qt.rooms.mixer_room — Qt BPM / key compatibility mixer.

Replaces phi.ui.rooms.mixer_room.MixerRoom (tk.Frame + tk.Canvas).

Shows the library as a grid of cells coloured by BPM range x Camelot key.
Below the grid, the current queue is shown as a chain of transitions with
compatibility indicators.

Room protocol: on_show(), on_refresh(), sync_transport()


Defines: _camelot_dist, _compat_color, _bpm_band, MixerRoom, __init__, _build, on_show, on_refresh, sync_transport, mark_playing, _build_grid, _on_cell_click, _build_chain

---

## Semantic links

→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]
→ [[engine-phi-player]]
→ [[engine-phi-session]]
→ [[PLAYBACK]]
→ [[engine-coherence-daemon]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-genre-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-queue-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-playlist-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-library-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-mini-transport-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
