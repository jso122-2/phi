# phi / ui / qt / rooms / library_room.py

#source #python

> path: phi/ui/qt/rooms/library_room.py  
> ext: .py  

---

# phi / ui / qt / rooms / library_room.py

phi.ui.qt.rooms.library_room — Qt full-page library browser with album spines.

Replaces phi.ui.rooms.library_room.LibraryPage (tk.Frame + tk.Canvas).

Layout
------
┌────────────────────────────────────────────────────────────────────┐
│  Library  [search ___________]  [+ Add Folder]   3a · 47al · 612t  │
├──────────┬─────────────────────────────────────────────────────────┤
│ Genre    │  album spines ← scroll →                                │
│          │  ┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐                    │
│  All     │  │  ││  ││  ││  ││  ││  ││  ││  │  ← QPainter spines  │
│▼ Electronic

Defines: _normalise_genre, _genres_for_track, _genre_label, _spine_color, _SpineCanvas, _LibrarySearchBar, LibraryPage, __init__, set_albums, paintEvent, mousePressEvent, mouseDoubleClickEvent, __init__, _build, _chip_style, _on_text_changed, _on_clear, _on_scope, _fire, text, scope, set_result_count, setFocusToEdit, __init__, _build, embed_tabs, toggle_deep, on_show, on_refresh, sync_transport, mark_playing, _build_genre_tree, _on_genre_click, _load_albums, _on_spine_select, _on_spine_double, _ctrl_menu, _on_spine_ctrl, _on_track_double, _on_track_clicked

---

## Semantic links

→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]
→ [[engine-phi-player]]
→ [[scripts-embed-tracks]]
→ [[engine-phi-session]]
→ [[engine-vault-garden]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-genre-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-mini-transport-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-playlist-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-mixer-room-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
