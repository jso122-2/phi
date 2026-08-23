# spotify-pipeline / scheduler

#spotify-pipeline #scheduler #CODE #hub

**File:** `pipeline/scheduler.py`

## Purpose

Converts a `LibrarySnapshot` into a flat list of `Job` objects ready to be enqueued. The only place that knows about chunking strategy.

## Chunking Strategy

| Collection | Strategy | Rationale |
|---|---|---|
| Liked songs | 100-track chunks | Crash safety — mid-batch failure loses at most 100 tracks |
| Albums | One job per album | Small (<20 tracks), track-number template requires co-location |
| Playlists | 100-track chunks | Same as liked songs |

## Functions

- `build_jobs(snap, out_root, fmt, chunk_size=100) -> list[Job]`
- `build_cache_jobs(track_urls, out_root, fmt, chunk_size=100) -> list[Job]`

## Connections

→ [[spotify-pipeline/index|spotify-pipeline]]
→ [[spotify-pipeline/fetcher|fetcher]]
→ [[spotify-pipeline/queue|queue]]
→ [[spotify-pipeline/worker|worker]]

---

## Auto-linked

→ [[index]]
→ [[mcp-server]]
→ [[config]]
→ [[indexer]]
→ [[obsidian-exporter]]
→ [[cursor-skills]]

→ [[fetcher]]
→ [[queue]]
→ [[worker]]
→ [[auth]]
→ [[2026-07-16-liked-songs-mullvad-multi-source-pipeline]]
→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]

→ [[2026-07-16-011935-modular-pipeline-rebuild]]
→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]
→ [[HOME]]
→ [[2026-07-15]]

→ [[2026-07-16-011935-mamba-environment-spotify-rip]]
→ [[2026-07-16-011935-spotify-rip-slash-commands]]
→ [[2026-07-16-011935-scribble-files-are-read-only]]
→ [[2026-07-16-011935-session-init]]
→ [[2026-07-16-011935-cursor-hooks-configuration]]
→ [[2026-07-16-011935-mcp-tool-command-reference]]

→ [[2026-07-16-011935-find]]
→ [[dev]]
→ [[2026-07-16-011935-run-shell-commands]]
→ [[2026-07-16-011935-dev-workhorse-development-mode]]
→ [[2026-07-16-011935-talk-conversational-context-mode]]
→ [[2026-07-16-011935-clean-repo-file-tree-cleanup]]
