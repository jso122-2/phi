# spotify-pipeline / fetcher

#spotify-pipeline #fetcher #CODE #hub

**Files:** `pipeline/fetcher/`

## Purpose

Fetches the full Spotify library from the API: liked songs, playlists, saved albums. Returns a `LibrarySnapshot` dataclass.

## Modules

| File | Purpose |
|---|---|
| `models.py` | Dataclasses: TrackInfo, PlaylistInfo, AlbumInfo, LibrarySnapshot |
| `_helpers.py` | retry_call(), paginate(), track_from_item() |
| `playlists.py` | fetch_playlists() with 403 fallback + cache recovery |
| `liked.py` | Fetch liked songs |
| `albums.py` | Fetch saved albums |
| `snapshot_io.py` | Save/load LibrarySnapshot as JSON |
| `cache_scraper.py` | Scrape Spotify desktop app's LevelDB cache for track URLs |

## Key Behaviours

**retry_call()** — wraps Spotify API calls with retry logic:
- 403: one soft retry after 4s (transient token-refresh boundary)
- 429: respects `Retry-After` header + 2s padding
- 5xx: exponential backoff (2, 4, 8, 16s), up to 4 attempts

**paginate()** — transparent Spotify pagination (50 items/page, 0.1s pacing between pages)

**fetch_playlists()** — 403 mid-stream handling:
- Got partial tracks before 403 → keep them
- Got 0 tracks, snapshot cache available → use cache
- Got 0 tracks, no cache → mark `forbidden=True`
- `owner_id` filter: only playlists owned by the user (not followed ones)

## Data Models

```python
TrackInfo(name, artists, album, spotify_url, track_number)
PlaylistInfo(name, owner, spotify_url, playlist_id, total_tracks, tracks, forbidden)
AlbumInfo(name, artists, year, spotify_url, album_id, total_tracks, tracks)
LibrarySnapshot(liked_tracks, playlists, albums)
```

## Connections

→ [[spotify-pipeline/index|spotify-pipeline]]
→ [[spotify-pipeline/scheduler|scheduler]]
→ [[spotify-pipeline/obsidian-exporter|obsidian-exporter]]

---

## Auto-linked

→ [[index]]
→ [[scheduler]]
→ [[mcp-server]]
→ [[config]]
→ [[indexer]]
→ [[obsidian-exporter]]

→ [[cursor-skills]]
→ [[auth]]
→ [[queue]]
→ [[worker]]
→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]
→ [[2026-07-16-liked-songs-mullvad-multi-source-pipeline]]

→ [[2026-07-16-011935-modular-pipeline-rebuild]]
→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]
→ [[2026-07-15]]
→ [[HOME]]

→ [[2026-07-16-011935-mamba-environment-spotify-rip]]
→ [[2026-07-16-011935-session-init]]
→ [[2026-07-16-011935-spotify-rip-slash-commands]]
→ [[2026-07-16-011935-scribble-files-are-read-only]]
→ [[2026-07-16-011935-slash-commands-spotify-rip]]
→ [[2026-07-16-011935-cursor-hooks-configuration]]

→ [[2026-07-16-011935-find]]
→ [[2026-07-16-011935-run-shell-commands]]
→ [[dev]]
→ [[2026-07-16-011935-talk-conversational-context-mode]]
→ [[2026-07-16-011935-dev-workhorse-development-mode]]
→ [[2026-07-16-011935-clean-repo-file-tree-cleanup]]
