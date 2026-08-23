# spotify-pipeline / cursor-skills.md

#doc #md

> path: spotify-pipeline/cursor-skills.md  
> ext: .md  

---

# spotify-pipeline / cursor-skills

#spotify-pipeline #cursor #agent-context

**Files:** `.cursor/skills/`

## Available Skills

| Skill | Trigger | Purpose |
|---|---|---|
| `download-playlist` | `/download-playlist <id>` | Download a Spotify playlist to disk via spotdl |
| `list-playlists` | `/list-playlists` | List all playlists on the account |
| `queue-status` | `/queue-status` | Show pending/downloading/done/failed job counts |
| `retry-failed` | `/retry-failed` | Reset all failed jobs back to pending |

## How Skills Map to MCP Tools

All four tools are served by [[spotify-pipeline/mcp-server|mcp-server]] via FastMCP stdio transport.

```
/list-playlists         →  list_playlists()
/download-playlist <id> →  download_playlist(id)
/queue-status           →  queue_status()
/retry-failed           →  retry_failed()
```

## Connections

→ [[spotify-pipeline/index|spotify-pipeline]]
→ [[spotify-pipeline/mcp-server|mcp-server]]
→ [[agent-context]]

---

## Auto-linked

→ [[index]]
→ [[config]]
→ [[mcp-server]]
→ [[obsidian-exporter]]
→ [[queue]]
→ [[scheduler]]

→ [[indexer]]
→ [[auth]]
→ [[fetcher]]
→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]
→ [[worker]]
→ [[HOME]]

→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]
→ [[2026-07-16-011935-spotify-rip-slash-commands]]
→ [[2026-07-16-011935-mcp-tool-command-reference]]
→ [[2026-07-16-011935-session-init]]

→ [[2026-07-16-011935-mamba-environment-spotify-rip]]
→ [[2026-07-16-011935-modular-pipeline-rebuild]]
→ [[2026-07-16-011935-cursor-hooks-configuration]]
→ [[2026-07-16-011935-slash-commands-spotify-rip]]
→ [[2026-07-16-011935-scribble-files-are-read-only]]
→ [[2026-07-16-011935-find]]

→ [[2026-07-16-011935-run-shell-commands]]
→ [[dev]]
→ [[mcp-server-server]]
→ [[2026-07-16-011935-talk-conversational-context-mode]]
→ [[2026-07-16-011935-dev-workhorse-development-mode]]
→ [[mcp-server-tools-system]]

---

## Semantic links

→ [[cursor-skills]]
→ [[mcp-server]]
→ [[fetcher]]
→ [[indexer]]
→ [[index]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-mcp-server-md]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-fetcher-md]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-indexer-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-spotify-importer-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-playlist-store-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
