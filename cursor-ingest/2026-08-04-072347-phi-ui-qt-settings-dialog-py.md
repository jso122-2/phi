# phi / ui / qt / settings_dialog.py

#source #python

> path: phi/ui/qt/settings_dialog.py  
> ext: .py  

---

# phi / ui / qt / settings_dialog.py

phi.ui.qt.settings_dialog — PySide6 preferences dialog.

Replaces phi.ui.settings_dialog.SettingsDialog (tk.Toplevel).

Sections
--------
  General  — watched folder, auto-scan, notifications
  Audio    — crossfade slider, ReplayGain, gapless
  Last.fm  — API credentials + OAuth flow
  CAIRRN   — live forest floor read-out
  About    — version, links

Public surface
--------------
    SettingsDialog(parent, ctrl)  — QDialog, call .exec() to open modal
    load_settings() → dict        — re-exported from phi.ui.settings_dialog
    save_settings(data)           — re-exported from phi.ui.settings

Defines: SettingsDialog, __init__, _build, _build_general, _build_audio, _build_lastfm, _build_cairrn, _refresh_cairrn, _build_about, _show_section, _sec_style, _scrollable_page, _h, _note, _cb_style, _entry_style, _browse_folder, _authorize_lastfm, _complete_lastfm, _on_lfm_connected, _save_and_close, _exchange

---

## Semantic links

→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]
→ [[engine-coherence-daemon]]
→ [[engine-phi-session]]
→ [[engine-phi-player]]
→ [[engine-cairrn-scheduler]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-settings-dialog-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-onboarding-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-app-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-app-overlays-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
