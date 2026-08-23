# phi / ui / qt / sidebar.py

#source #python

> path: phi/ui/qt/sidebar.py  
> ext: .py  

---

# phi / ui / qt / sidebar.py

phi.ui.qt.sidebar — PySide6 sidebar panel.

Replaces phi.ui.sidebar.SidebarPanel.

Starts hidden (same as the Tk version).  Press the sidebar hotkey (⌘B) to
reveal it.  The execute_cmd logic is preserved verbatim — only the Tkinter
display layer (tk.Text + tk.Entry) is replaced with QTextBrowser + QLineEdit.

Public API (mirrors SidebarPanel)
-----------------------------------
    update_queue(queue, pos, library)
    update_info(path, meta, ann)
    execute_cmd(raw) -> str
    focus_repl()
    toggle()


Defines: _trunc, SidebarWidget, __init__, _build, update_queue, update_info, execute_cmd, focus_repl, toggle, _render, _on_enter, _clear_feedback, keyPressEvent, row, _fmt, hdr, sep

---

## Semantic links

→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]
→ [[scripts-burn-gui]]
→ [[engine-phi-session]]
→ [[engine-cairrn-dispatch]]
→ [[engine-hot-loader]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-overlay-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-jim-help-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-keys-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-now-playing-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
