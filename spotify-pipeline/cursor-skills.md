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

All four tools are served by [[spotify-pipeline/pipeline-mcp-server|mcp-server]] via FastMCP stdio transport.

```
/list-playlists         →  list_playlists()
/download-playlist <id> →  download_playlist(id)
/queue-status           →  queue_status()
/retry-failed           →  retry_failed()
```

## Connections

→ [[spotify-pipeline/spotify-pipeline-index|spotify-pipeline]]
→ [[spotify-pipeline/pipeline-mcp-server|mcp-server]]
→ [[agent-context]]

---

## Auto-linked

→ [[spotify-pipeline-index]]
→ [[config]]
→ [[pipeline-mcp-server]]
→ [[obsidian-exporter]]
→ [[queue]]
→ [[scheduler]]

→ [[indexer]]
→ [[auth]]
→ [[fetcher]]
→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]
→ [[worker]]
→ [[HOME]]



→ [[dev]]
→ [[mcp-server-server]]
→ [[mcp-server-tools-system]]
