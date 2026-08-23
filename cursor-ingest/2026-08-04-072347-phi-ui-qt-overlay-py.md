# phi / ui / qt / overlay.py

#source #python

> path: phi/ui/qt/overlay.py  
> ext: .py  

---

# phi / ui / qt / overlay.py

phi.ui.qt.overlay — PySide6 ⌘K command palette.

Replaces phi.ui.overlay.CommandOverlay.

Built once, shown/hidden via show()/hide().  Async recent-track fetch keeps
the window responsive (same pattern as the Tk version we already hardened).

Public API (mirrors CommandOverlay)
--------------------------------------
    show()
    hide()


Defines: CommandOverlay, __init__, _build, show, hide, keyPressEvent, _on_text_changed, _search, _fetch_recent_async, _set_results, _render_results, _activate_current, _reposition, _work

---

## Semantic links

→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]
→ [[mcp-server-tools-phi-clip]]
→ [[engine-phi-player]]
→ [[engine-vault-garden]]
→ [[engine-cairrn-dispatch]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-jim-help-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-app-overlays-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-sidebar-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-settings-dialog-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
