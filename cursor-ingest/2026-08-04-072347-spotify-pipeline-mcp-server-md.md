# spotify-pipeline / mcp-server.md

#doc #md

> path: spotify-pipeline/mcp-server.md  
> ext: .md  

---

# spotify-pipeline / mcp-server

#spotify-pipeline #mcp #CODE #hub

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

→ [[spotify-pipeline/index|spotify-pipeline]]
→ [[spotify-pipeline/auth|auth]]
→ [[spotify-pipeline/fetcher|fetcher]]
→ [[spotify-pipeline/queue|queue]]
→ [[spotify-pipeline/worker|worker]]
→ [[spotify-pipeline/obsidian-exporter|obsidian-exporter]]

---

## Auto-linked

→ [[index]]
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

→ [[2026-07-16-011935-modular-pipeline-rebuild]]
→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]
→ [[2026-07-16-011935-session-init]]
→ [[HOME]]

→ [[2026-07-16-011935-mamba-environment-spotify-rip]]
→ [[2026-07-16-011935-spotify-rip-slash-commands]]
→ [[2026-07-16-0119

---

## Semantic links

→ [[mcp-server]]
→ [[cursor-skills]]
→ [[index]]
→ [[fetcher]]
→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-cursor-skills-md]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-fetcher-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-spotify-importer-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-server-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-server-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
