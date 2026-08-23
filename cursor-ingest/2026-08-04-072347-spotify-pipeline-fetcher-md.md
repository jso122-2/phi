# spotify-pipeline / fetcher.md

#doc #md

> path: spotify-pipeline/fetcher.md  
> ext: .md  

---

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
→ [[2026-07-15-spotify-pipeli

---

## Semantic links

→ [[fetcher]]
→ [[index]]
→ [[pipeline-fetcher-models]]
→ [[mcp-server]]
→ [[pipeline-sources-youtube-music]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-pipeline-fetcher-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-fetcher-models-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-init-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-fetcher-models-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-indexer-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
