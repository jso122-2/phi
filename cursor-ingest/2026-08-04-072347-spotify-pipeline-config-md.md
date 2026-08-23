# spotify-pipeline / config.md

#doc #md

> path: spotify-pipeline/config.md  
> ext: .md  

---

# spotify-pipeline / config

#spotify-pipeline #config #CODE #hub

**Files:** `config/config.yaml`, `pipeline/utils/config.py`, `.env`

## Environment Variables (.env)

```dotenv
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```

Credentials never go in `config.yaml`. Loaded via python-dotenv.

## Key Config Sections

- `download.output_dir` — `/Users/jacksonmacleod/Desktop/Spotify`
- `download.intermediate_format` — `mp3`
- `download.bitrate` — `320k`
- `download.chunk_size` — `100`
- `obsidian.vault_path` — `/Users/jacksonmacleod/Documents/Spotify-Rip/Spotify-rip`
- `obsidian.subdir` — `spotify`
- `playlists.owned_only` — `true`

## Dependencies

```
spotipy>=2.23.0, spotdl>=4.3.0, python-dotenv>=1.0.0
pyyaml>=6.0, colorlog>=6.8.0, rich>=13.7.0
tqdm>=4.66.0, mutagen>=1.47.0, mcp[cli]>=1.12.0
```

Dev: `ruff`, `mypy`, `pytest`, `detect-secrets`, `pre-commit`

## Connections

→ [[spotify-pipeline/index|spotify-pipeline]]
→ [[spotify-pipeline/auth|auth]]
→ [[spotify-pipeline/mcp-server|mcp-server]]

---

## Auto-linked

→ [[index]]
→ [[cursor-skills]]
→ [[mcp-server]]
→ [[auth]]
→ [[obsidian-exporter]]
→ [[scheduler]]

→ [[indexer]]
→ [[queue]]
→ [[fetcher]]
→ [[worker]]
→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]
→ [[HOME]]

→ [[2026-07-16-liked-songs-mullvad-multi-source-pipeline]]
→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]
→ [[2026-07-16-011935-mamba-environment-spotify-rip]]

→ [[2026-07-16-011935-modular-pipeline-rebuild]]
→ [[2026-07-16-011935-spotify-rip-slash-commands]]
→ [[2026-07-16-011935-session-init]]
→ [[2026-07-16-011935-scribble-files-are-read-only]]
→ [[2026-07-16-011935-mcp-tool-command-reference]]
→ [[2026-07-16-011935-slash-commands-spotify-rip]]

→ [[2026-07-16-011935-find]]
→ [[2026-07-16-011935-cursor-hooks-configuration]]
→ [[dev]]
→ [[2026-07-16-011935-run-shell-commands]]
→ [[2026-07-16-011935-dev-workhorse-development-mode]]
→ [[mcp-server-server]]

---

## Semantic links

→ [[config]]
→ [[auth]]
→ [[index]]
→ [[scripts-run]]
→ [[fetcher]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-pipeline-init-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-auth-md]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-run-md]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-fetcher-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-fetcher-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
