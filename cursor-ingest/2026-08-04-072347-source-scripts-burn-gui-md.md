# source / scripts-burn-gui.md

#doc #md

> path: source/scripts-burn-gui.md  
> ext: .md  

---

# scripts/burn_gui

#code #module #scripts #code

> source_path: scripts/burn_gui.py  
> package: scripts  
> module: scripts/burn_gui  
> hub: CODE  
> created_ts:   

---

**Package:** `scripts`  
**Module:** `scripts/burn_gui`  
**Source:** `scripts/burn_gui.py`

burn_gui.py — Google Keep Backwards Burner
Pygame desktop GUI (fully local, no browser/server).

Flow:
  LAUNCH     → kills Chrome, relaunches with real profile + CDP
  ⊕ TARGET  → confirm you're on the right Keep page
  START BURN → overwrites every note with garbage, then deletes all
  ABORT      → stops cleanly after current note

Run:
    python scripts/burn_gui.py

## API

- `def garbage`
- `async def detect_note_selector`
- `async def find_body`
- `async def close_note`
- `async def overwrite_note`
- `async def delete_first_note`
- `async def scroll_load_all`
- `async def run_burn`
- `class Button` — Simple pygame button.
- `class BurnGUI` — Pygame implementation of the burn GUI.
- `async def _main`

---

## Semantic links

→ [[2026-07-21-000947-clean-the-entire-misc-folder-top-to-bottom]]
→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]
→ [[2025-09-09-102444-2025-09-09t20-25-19-520-10-00]]
→ [[2025-09-24-132835-2025-09-24t23-28-36-054-10-00]]
→ [[2025-05-15-081254-2025-05-15t18-22-57-859-10-00]]

## Related notes

→ [[source/scripts-backwards-burn]]
→ [[source/mcp-server-tools-system]]
→ [[source/engine-phi-player]]
→ [[source/tools-keep-ingest]]
→ [[source/scripts-rescrape-short]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[scripts-backwards-burn]]
→ [[scripts-index]]
→ [[index]]
→ [[2025-10-06-150602-2025-10-07t02-07-04-211-11-00]]
→ [[2025-09-09-072136-2025-09-09t17-21-36-865-10-00]]
→ [[2025-05-28-154122-dawn-test-1]]

---

## Semantic links

→ [[scripts-burn-gui]]
→ [[scripts-backwards-burn]]
→ [[2026-07-28-230105-remaining-refactor-pass-port-all-remaining]]
→ [[scripts-run]]
→ [[scripts-train]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-scripts-burn-gui-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-backwards-burn-md]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-run-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-main-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
