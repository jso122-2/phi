# spotify-pipeline / mcp-server

#spotify-pipeline #mcp #CODE 

**File:** `pipeline/mcp_server.py`

## Purpose

FastMCP server that exposes the Spotify pipeline to Cursor agents via stdio transport.

## Tools

| Tool | Description |
|---|---|
| `list_playlists()` | Return all playlists on the authenticated account as JSON |
| `download_playlist(playlist_id)` | Fetch + download a single playlist end-to-end |
| `queue_status()` | Show batch CLI queue stats (pending/done/failed) |
| `retry_failed()` | Reset all failed batch jobs to pending |
| `vault_export()` | Export library snapshot as linked .md notes into vault |

## download_playlist Flow

1. Fetch playlist metadata (single API call)
2. Enumerate all tracks (paginated, 0.02s pacing)
3. Build 100-track chunk jobs
4. Run spotdl sequentially for each chunk
5. Return summary with counts and errors

## vault_export Flow

1. Read `data/library_snapshot.json`
2. Read `obsidian.*` config from `config/config.yaml`
3. Run ObsidianExporter.export()
4. Return JSON summary of note counts
5. Caller should call samba_refresh to re-index

## Running

```bash
.venv/bin/python -m pipeline.mcp_server
```

## Connections

→ [[spotify-pipeline/spotify-pipeline-index|spotify-pipeline]]
→ [[spotify-pipeline/auth|auth]]
→ [[spotify-pipeline/fetcher|fetcher]]
→ [[spotify-pipeline/queue|queue]]
→ [[spotify-pipeline/worker|worker]]
→ [[spotify-pipeline/obsidian-exporter|obsidian-exporter]]

---

## Auto-linked

→ [[spotify-pipeline-index]]
→ [[cursor-skills]]
→ [[config]]
→ [[obsidian-exporter]]
→ [[scheduler]]
→ [[indexer]]

→ [[queue]]
→ [[fetcher]]
→ [[auth]]
→ [[worker]]
→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]
→ [[2026-07-16-liked-songs-mullvad-multi-source-pipeline]]

→ [[HOME]]


→ [[dev]]
→ [[mcp-server-tools-system]]
