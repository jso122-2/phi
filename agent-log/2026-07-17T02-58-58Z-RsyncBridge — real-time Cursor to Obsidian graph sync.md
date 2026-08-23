---
title: "RsyncBridge — real-time Cursor to Obsidian graph sync"
created: 2026-07-17T02:58:58.118845+00:00
zone: agent-log
tags: [agent-log]
---
# RsyncBridge — real-time Cursor to Obsidian graph sync

## What it does

The RsyncBridge daemon (`engine/rsync_bridge.py`) creates a direct, real-time link between Cursor file saves and the Obsidian knowledge graph, replacing the 5-minute polling cycle with sub-second event delivery.

## Architecture

File saved in watched dir → watchdog kqueue/inotify event → ChangeBuffer debounce (400ms) → `SambaOrchestrator.refresh()` in-process → graph updated.

A threading lock prevents concurrent crawl storms when multiple files change rapidly.

## Vault stubs

For every changed source file (outside the vault), the bridge writes a minimal `.md` stub into `agent-stubs/code-mirror/` so the file immediately has a graph node before the full re-encode propagates its BERT embeddings.

## Deployment

Runs as a persistent `launchd` agent (`com.samba-gnn.rsync-bridge.plist`). Install with `bash install_rsync_bridge.sh`. Manages itself: `KeepAlive=true`, throttle 10s, auto-restarts on crash.

## Config changes

- `rescan_interval_seconds` lowered from 300 → 30 (fallback only; bridge handles instant updates)
- `.env` corrected: `OBSIDIAN_VAULT_PATH` was pointing at Spotify-Rip, now points at `~/Documents/obsidian-vault`
- `watchdog>=4.0.0` added to `requirements.txt`

## Log

`logs/rsync_bridge.log` — live bridge events and crawl summaries.

## Related Notes

---

## Auto-linked

→ [[logger]]

→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[sessions]]
→ [[graph]]
→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]
→ [[git-log]]
→ [[2026-07-13-095004-cairrnify-the-mcp-server-fix-dom-queue-open]]

→ [[graph-logger]]
→ [[graph-init]]
→ [[engine-rsync-bridge]]
→ [[mcp-server-tools-graph]]
→ [[graph-node]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
