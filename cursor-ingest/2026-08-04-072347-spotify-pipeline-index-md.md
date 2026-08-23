# spotify-pipeline / index.md

#doc #md

> path: spotify-pipeline/index.md  
> ext: .md  

---

# spotify-pipeline

#spotify-pipeline #agent-context #CODE

Python pipeline that downloads your entire Spotify library (liked songs, playlists, saved albums) as audio via spotdl (YouTube Music source), then generates M3U playlist files.

**Repo:** `/Users/jacksonmacleod/Projects/spotify-pipeline`

## Architecture

```
Auth (spotipy OAuth) → Fetch library → Download audio (spotdl) → Export M3U
                                               ↕
                                       Queue (SQLite WAL)
                                               ↕
                                       Indexer (SQLite)
                                               ↕
                                       Obsidian Vault Export
```

## Modules

| Module | Purpose |
|---|---|
| [[spotify-pipeline/auth|auth]] | Spotify OAuth — local callback server, token caching |
| [[spotify-pipeline/fetcher|fetcher]] | Fetches library data from Spotify API |
| [[spotify-pipeline/scheduler|scheduler]] | Converts LibrarySnapshot → chunked Job list |
| [[spotify-pipeline/queue|queue]] | SQLite-backed job queue with atomic claim + exponential backoff |
| [[spotify-pipeline/worker|worker]] | Thread pool that drains the queue via spotdl |
| [[spotify-pipeline/indexer|indexer]] | Tracks downloaded files; SQLite index |
| [[spotify-pipeline/obsidian-exporter|obsidian-exporter]] | Exports library data as linked .md notes into vault |
| [[spotify-pipeline/mcp-server|mcp-server]] | FastMCP server exposing pipeline tools to Cursor agents |
| [[spotify-pipeline/config|config]] | Config loading (YAML + .env) |
| [[spotify-pipeline/cursor-skills|cursor-skills]] | Cursor agent skills for agent-driven downloads |

## Config

- **Vault path:** `/Users/jacksonmacleod/Documents/Spotify-Rip/Spotify-rip`
- **Output dir:** `/Users/jacksonmacleod/Desktop/Spotify`
- **Format:** mp3 @ 320k (intermediate)
- **Chunk size:** 100 tracks per spotdl job

## Connections

→ [[HOME]]
→ [[agent-context]]
→ [[CODE]]
→ [[spotify-pipeline/

---

## Semantic links

→ [[index]]
→ [[fetcher]]
→ [[mcp-server]]
→ [[indexer]]
→ [[scheduler]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-fetcher-md]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-indexer-md]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-mcp-server-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-init-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-fetcher-models-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
