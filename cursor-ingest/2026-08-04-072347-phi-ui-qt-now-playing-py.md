# phi / ui / qt / now_playing.py

#source #python

> path: phi/ui/qt/now_playing.py  
> ext: .py  

---

# phi / ui / qt / now_playing.py

phi.ui.qt.now_playing — PySide6 full-spectrum ASCII album art panel.

Replaces phi.ui.now_playing.NowPlayingPanel.

The ASCII grid is computed entirely off the main thread (same prefeed_art /
commit_art pattern as the Tkinter version) and painted via QPainter in
paintEvent.  No HTML, no QTextEdit — pure painter path.

Public API (mirrors NowPlayingPanel)
--------------------------------------
    set_track(path, meta)
    set_title_only(path)
    set_art(art_bytes)
    prefeed_art(art_bytes, cols, rows, on_ready=None)
    commit_art()
    commit_art_or_wait(on_ready)
    reset()
    set_rating

Defines: _placeholder_grid, NowPlayingWidget, __init__, paintEvent, resizeEvent, sizeHint, set_track, set_title_only, set_art, set_rating, prefeed_art, commit_art, commit_art_or_wait, reset, _set_grid, _render, _run

---

## Semantic links

→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]
→ [[scripts-bake-ascii]]
→ [[2026-07-16T19-50-20Z-phi floating UI + ASCII waveform — Layer 5 implementation]]
→ [[engine-phi-player]]
→ [[scripts-burn-gui]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-sidebar-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-app-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-art-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-overlay-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
