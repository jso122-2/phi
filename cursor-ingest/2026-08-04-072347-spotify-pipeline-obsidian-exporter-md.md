# spotify-pipeline / obsidian-exporter.md

#doc #md

> path: spotify-pipeline/obsidian-exporter.md  
> ext: .md  

---

# spotify-pipeline / obsidian-exporter

#spotify-pipeline #obsidian #CODE

**File:** `pipeline/obsidian/exporter.py`

## Purpose

Exports the Spotify library (LibrarySnapshot) as linked Markdown notes into this Obsidian vault. Creates one note per artist, album, and playlist.

## Output Layout in Vault

```
{vault}/spotify/
  spotify.md             ← root index with summary table
  artists/{slug}.md      ← one note per artist
  albums/{slug}.md       ← one note per saved album
  playlists/{slug}.md    ← one note per accessible playlist
```

## Wikilink Strategy

- Slugs: lowercase, spaces→dashes, special chars stripped, max 80 chars
- Every note links back to `[[spotify|Spotify Library]]`
- Vault hub connections: `[[HOME]]`, `[[agent-context]]`

## Tags Applied

- Artist notes: `#spotify #artist`
- Album notes: `#spotify #album`
- Playlist notes: `#spotify #playlist`
- Index note: `#spotify #library #agent-context`

## Triggering Export

```bash
# Via MCP tool (from Cursor agent):
vault_export()

# Requires data/library_snapshot.json (run fetch step first):
python run.py --fetch-only
```

After export, call samba_refresh to re-index the vault in the GNN.

## Connections

→ [[spotify-pipeline/index|spotify-pipeline]]
→ [[spotify-pipeline/fetcher|fetcher]]
→ [[spotify-pipeline/mcp-server|mcp-server]]
→ [[HOME]]
→ [[agent-context]]

---

## Auto-linked

→ [[index]]
→ [[mcp-server]]
→ [[config]]
→ [[cursor-skills]]
→ [[scheduler]]
→ [[indexer]]

→ [[fetcher]]
→ [[auth]]
→ [[queue]]
→ [[worker]]
→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]
→ [[COMMANDS]]

→ [[2026-07-16-011935-spotify-rip-slash-commands]]
→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]
→ [[2026-07-16-011935-slash-commands-spotify-rip]]

→ [[2026-07-16-011935-mamba-environment-spotify-rip]]
→ [[2026-07-16-011935-modular-pipeline-rebuild]]
→ [[2026-07-16-011935-mcp-tool-command-reference]]
→ [[2026-07-16-011935-scribble-files-are-read-only]]
→ [[2026-07-16-011935-session-init]]
→

---

## Semantic links

→ [[obsidian-exporter]]
→ [[graph-node]]
→ [[fetcher]]
→ [[indexer]]
→ [[index]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-fetcher-md]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-indexer-md]]
→ [[cursor-ingest/2026-08-04-072347-graph-node-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-graph-node-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
