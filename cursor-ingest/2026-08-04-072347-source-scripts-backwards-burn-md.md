# source / scripts-backwards-burn.md

#doc #md

> path: source/scripts-backwards-burn.md  
> ext: .md  

---

# scripts/backwards_burn

#code #module #scripts #code

> source_path: scripts/backwards_burn.py  
> package: scripts  
> module: scripts/backwards_burn  
> hub: CODE  
> created_ts:   

---

**Package:** `scripts`  
**Module:** `scripts/backwards_burn`  
**Source:** `scripts/backwards_burn.py`

backwards_burn.py — Google Keep backwards burner.

Overwrites every note in your Google Keep with random garbage text,
then deletes all notes. Content becomes permanently unreadable.

Run with:
    python backwards_burn.py

A Chromium window opens. Log in normally, press Enter in the terminal
when your notes are visible, then let it rip.

## API

- `def _adjacent_key` — Return a nearby key for a realistic typo.
- `async def human_move` — Move mouse along a slight arc to (x, y) from current position.
- `async def human_click`
- `async def human_type` — Type text with randomised delays and occasional corrected typos.
- `def wait_for_spacebar` — Block until the user presses the spacebar key.
- `async def auto_login` — Attempt to fill email + password with human-like behaviour.
- `def garbage` — Return a random string of printable noise.
- `def garbage_title`
- `def garbage_body`
- `async def find_body` — Return the first visible body field, trying each selector.
- `async def close_open_note` — Close an open note dialog — try Close button, then Escape.
- `async def overwrite_one_note` — Click card at position card_idx, overwrite title + body with garbage,
- `async def delete_one_note` — Delete the first visible note card via its overflow menu.
- `async def scroll_to_load_all` — Scroll the page to force lazy-loading of all notes.
- `async def main`

---

## Semantic links

→ [[2026-07-21-000947-clean-the-entire-misc-folder-top-to-bottom]]
→ [[index]]
→ [[2025-05-15-081254-2025-05-15t18-22-57-859-10-00]]
→ [[2025-09-09-102444-2025-09-09t20-25-19-520-10-00]]
→ [[2024-09-09-102537-website-creation-scribble]]

## Related notes

→ [[source/scripts-burn-gui]]
→ [[source/scripts-rescrap

---

## Semantic links

→ [[scripts-backwards-burn]]
→ [[scripts-burn-gui]]
→ [[tools-fix-dead-links]]
→ [[scripts-rescrape-short]]
→ [[2025-05-15-081254-2025-05-15t18-22-57-859-10-00]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-scripts-backwards-burn-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-burn-gui-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-burn-gui-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-fix-dead-links-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
