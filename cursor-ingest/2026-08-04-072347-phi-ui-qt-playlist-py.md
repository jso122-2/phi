# phi / ui / qt / playlist.py

#source #python

> path: phi/ui/qt/playlist.py  
> ext: .py  

---

# phi / ui / qt / playlist.py

phi.ui.qt.playlist — PySide6 track-list panel.

Replaces phi.ui.playlist.PlaylistPanel.

Public API (mirrors PlaylistPanel)
------------------------------------
    search_var              — object with .get() / .set(str)
    refresh(queue, view, queue_pos, library)
    jump_to_current(queue_pos, view)
    flash_status(msg)
    set_watch(active, folder_name="")
    set_sort(key_or_none, rev=False)
    clear_search()
    scroll_up(units=3)
    scroll_down(units=3)
    jump_to_top()
    focus()


Defines: _GenreDotDelegate, _GenreLegend, _SearchVar, PlaylistWidget, paint, sizeHint, __init__, set_genres, __init__, get, set, __init__, _build, refresh, _do_refresh, _update_legend, showEvent, jump_to_current, flash_status, set_watch, set_sort, clear_search, scroll_up, scroll_down, jump_to_top, focus, _on_double_click, _edit_selected_tags, _remove_selected, _tb

---

## Semantic links

→ [[engine-phi-player]]
→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]
→ [[2026-07-16T19-50-20Z-phi floating UI + ASCII waveform — Layer 5 implementation]]
→ [[pipeline-sources-youtube-music]]
→ [[scripts-embed-tracks]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-playlist-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-queue-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-phi-player-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-transport-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-playlist-store-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
