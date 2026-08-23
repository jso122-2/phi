# phi / ui / qt / mini_player.py

#source #python

> path: phi/ui/qt/mini_player.py  
> ext: .py  

---

# phi / ui / qt / mini_player.py

phi.ui.qt.mini_player — compact always-on-top floating player.

Replaces phi.ui.mini_player.MiniPlayer (tk.Toplevel).

A borderless 320×72 QWidget that shows:
  ┌──────────────────────────────────────────┐
  │ [art]  Title                |<  ▶  >|  ✕ │
  │ [art]  Artist               ─────────── │
  └──────────────────────────────────────────┘

Drag by pressing anywhere on the window.
Toggle with ⌘M / toggle_mini_player().

Public API (mirrors MiniPlayer)
---------------------------------
    toggle()
    update_track(path, meta)
    set_playing(playing)


Defines: MiniPlayer, __init__, _build, toggle, update_track, set_playing, mousePressEvent, mouseMoveEvent, mouseReleaseEvent, _reset_art, _center

---

## Semantic links

→ [[engine-phi-player]]
→ [[2026-07-16T19-50-20Z-phi floating UI + ASCII waveform — Layer 5 implementation]]
→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-app-overlays-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-mini-transport-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-overlay-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-playlist-room-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
