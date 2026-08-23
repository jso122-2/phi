# phi / ui / qt / tag_editor.py

#source #python

> path: phi/ui/qt/tag_editor.py  
> ext: .py  

---

# phi / ui / qt / tag_editor.py

phi.ui.qt.tag_editor — PySide6 batch tag editor dialog.

Replaces phi.ui.tag_editor.TagEditorDialog (tk.Toplevel).

Usage
-----
    TagEditorDialog(parent, paths=["/path/a.mp3", ...]).exec()

The _read_tags / _write_tags functions are reused unchanged from
phi.ui.tag_editor (they are framework-agnostic).


Defines: TagEditorDialog, __init__, _build, _load_async, _populate, _save, _write_worker, _finish, _worker, _on_focus

---

## Semantic links

→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]
→ [[scripts-embed-tracks]]
→ [[engine-phi-session]]
→ [[tools-enrich-c7]]
→ [[scripts-backwards-burn]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-settings-dialog-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-settings-dialog-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-sidebar-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-app-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-onboarding-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
