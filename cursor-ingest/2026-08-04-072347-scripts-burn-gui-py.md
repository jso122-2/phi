# scripts / burn_gui.py

#source #python

> path: scripts/burn_gui.py  
> ext: .py  

---

# scripts / burn_gui.py


burn_gui.py — Google Keep Backwards Burner
Pygame desktop GUI (fully local, no browser/server).

Flow:
  LAUNCH     → kills Chrome, relaunches with real profile + CDP
  ⊕ TARGET  → confirm you're on the right Keep page
  START BURN → overwrites every note with garbage, then deletes all
  ABORT      → stops cleanly after current note

Run:
    python scripts/burn_gui.py


Defines: garbage, Button, BurnGUI, __init__, set_enabled, handle_event, draw, __init__, _build_buttons, log, set_status, set_note_count, set_progress, _on_launch, _on_target, _on_burn, _on_abort, handle_events, draw

---

## Semantic links

→ [[scripts-burn-gui]]
→ [[scripts-backwards-burn]]
→ [[2026-07-21-000947-clean-the-entire-misc-folder-top-to-bottom]]
→ [[2025-09-09-102444-2025-09-09t20-25-19-520-10-00]]
→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-scripts-burn-gui-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-backwards-burn-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-backwards-burn-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-app-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-index-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
