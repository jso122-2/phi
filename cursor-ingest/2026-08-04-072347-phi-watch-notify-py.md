# phi / watch / notify.py

#source #python

> path: phi/watch/notify.py  
> ext: .py  

---

# phi / watch / notify.py

phi.watch.notify — macOS track-change banners.

Sends a macOS notification when a new track starts playing.
Falls back silently on non-macOS or when permission is denied.

Two backend attempts in order:
  1. pync (wrapper around terminal-notifier) — richest: icon + group
  2. osascript AppleScript display notification — no extra deps

Usage
-----
    from phi.watch.notify import notify_track_change
    notify_track_change(title="Shine On", artist="Pink Floyd", album="WYWH")


Defines: notify_track_change, _send, _esc

---

## Semantic links

→ [[2026-07-21-000947-clean-the-entire-misc-folder-top-to-bottom]]
→ [[engine-phi-player]]
→ [[scripts-spawn-tracer]]
→ [[scripts-run]]
→ [[mcp-server-tools-phi-clip]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-watch-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-watcher-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-enrich-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-lastfm-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-race-watcher-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
