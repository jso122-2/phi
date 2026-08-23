# source / pipeline-auth.md

#doc #md

> path: source/pipeline-auth.md  
> ext: .md  

---

# pipeline/auth

#code #module #pipeline #code

> source_path: pipeline/auth.py  
> package: pipeline  
> module: pipeline/auth  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/auth`  
**Source:** `pipeline/auth.py`

pipeline.auth — Spotify OAuth with DNS-transient retry.

Key design (2026-07-16):
    Mullvad relay switching kills system DNS for ~2-5s.  Any network call
    during that window throws socket.gaierror.  _retry_network() wraps
    every outbound call with 6×5s retries specifically for that failure mode.

Public API
----------
    get_spotify_client() -> spotipy.Spotify
        Main entry point.  Reads credentials from .env, caches token to
        .cache/spotify_token.  Subsequent runs skip the browser entirely.

## API

- `def _retry_network` — Wrap a network call with retry logic for DNS transients.
- `def _parse_redirect_uri` — Extract (host, port, path) from a redirect URI.
- `class _OAuthCallbackHandler` — Minimal HTTP handler that captures the ?code= query parameter.
- `class _ReuseAddrServer`
- `def _wait_for_code` — Poll the local server until the OAuth ?code= arrives or timeout.
- `def get_spotify_client` — Build and return an authenticated spotipy.Spotify instance.

---

## Semantic links

→ [[auth]]
→ [[config]]
→ [[2026-07-16-liked-songs-mullvad-multi-source-pipeline]]
→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]
→ [[index]]

## Related notes

→ [[source/pipeline-vpn-mullvad]]
→ [[source/scripts-run]]
→ [[source/pipeline-vpn-egress]]
→ [[source/mcp-server-tools-system]]
→ [[source/pipeline-vpn-relay-pool]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[pipeline-worker-init]]
→ [[pipeline-fetcher-init]]
→ [[pipeline-index]]
→ [[pipeline-vpn-mullvad]]
→ [[pipeline-bridge-init]]
→ [[scripts-run]]

---

## Semantic links

→ [[pipeline-auth]]
→ [[auth]]
→ [[pipeline-vpn-mullvad]]
→ [[config]]
→ [[scripts-run]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-pipeline-auth-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-auth-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-vpn-mullvad-py]]
→ [[cursor-ingest/2026-08-04-072347-scripts-run-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-config-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
