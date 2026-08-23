# phi / ui / qt / rooms / __init__.py

#source #python

> path: phi/ui/qt/rooms/__init__.py  
> ext: .py  

---

# phi / ui / qt / rooms / __init__.py

phi.ui.qt.rooms — Qt room pages.

Each room from phi/ui/rooms/ is ported as a QWidget.
Rooms not yet ported remain as StubRoom placeholders.

Exports (all callable as ClassName(parent=..., ctrl=...))
---------------------------------------------------------
    QueueRoom       — live playback queue + CAIRRN dispatch panel (magnum opus)
    LibraryPage     — full library browser with album spines
    PlaylistRoom    — two-pane drag-and-build playlist studio
    MixerRoom       — BPM / key compatibility mixer
    GenreRoom       — full ASCII genre graph with fractal zoom
    MLDragonPage    — dr

Defines: StubRoom, ZSpinePage, __init__, refresh, update_transport, set_playing, on_show, on_refresh, sync_transport, mark_playing, __init__

---

## Semantic links

→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]
→ [[engine-phi-session]]
→ [[engine-coherence-daemon]]
→ [[engine-arm-injector]]
→ [[scripts-train]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-mini-transport-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-library-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-dragon-panel-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-genre-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-playlist-room-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
