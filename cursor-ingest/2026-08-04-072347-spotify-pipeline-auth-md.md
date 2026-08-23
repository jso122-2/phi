# spotify-pipeline / auth.md

#doc #md

> path: spotify-pipeline/auth.md  
> ext: .md  

---

# spotify-pipeline / auth

#spotify-pipeline #auth #CODE #hub

**File:** `pipeline/auth.py`

## Purpose

Handles Spotify OAuth with a full local callback server. Owns the complete handshake:
1. Parse redirect URI (extracts host + port)
2. Start `_ReuseAddrServer` (SO_REUSEADDR) before opening browser
3. Open Spotify auth URL in default browser
4. Catch `?code=` redirect on local server
5. Exchange code for access + refresh token via spotipy
6. Cache token to `.cache/spotify_token` (mode 0o700)

## Key Details

- **Scopes:** `user-library-read`, `playlist-read-private`, `playlist-read-collaborative`, `user-follow-read`
- **Auth timeout:** 120 seconds
- **Token cache:** `.cache/spotify_token` — subsequent runs skip the browser entirely
- **Refresh:** Silent token refresh on expiry (no browser needed)
- **Redirect URI:** Must include explicit port (e.g. `http://localhost:8888/callback`)

## Functions

- `get_spotify_client() -> spotipy.Spotify` — main entry point; reads from `.env`
- `_parse_redirect_uri(uri)` — extracts (host, port, path)
- `_wait_for_code(server, timeout)` — polls for OAuth code with 0.2s sleep

## Connections

→ [[spotify-pipeline/index|spotify-pipeline]]
→ [[spotify-pipeline/mcp-server|mcp-server]]
→ [[spotify-pipeline/config|config]]

---

## Auto-linked

→ [[config]]
→ [[index]]
→ [[mcp-server]]
→ [[cursor-skills]]
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

→ [[2026-07-16-011935-spotify-rip-slash-commands]]
→ [[2026-07-16-011935-modular-pipeline-rebuild]]
→ [[2026-07-16-011935-mamba-environment-spotify-rip]]
→ [[2026-07-16-011935-session-init]]
→ [[2026-07-16-011935-mcp-tool-command-reference]]
→ [[2026-07-16-011935-slash-commands-spotify-rip]]

→ [[2026-07-16-011935-scribble-files-are-read-only]]
→ [[pipelin

---

## Semantic links

→ [[auth]]
→ [[config]]
→ [[pipeline-auth]]
→ [[index]]
→ [[fetcher]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-config-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-auth-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-auth-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-run-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
