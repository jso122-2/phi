# pipeline / vpn / mullvad.py

#source #python

> path: pipeline/vpn/mullvad.py  
> ext: .py  

---

# pipeline / vpn / mullvad.py


pipeline.vpn.mullvad — Mullvad CLI wrapper for the spotify-pipeline.

Three public entry points used by run.py:
    ensure_sweden()   — connect to a Swedish relay; idempotent
    allow_lan()       — permit LAN traffic while VPN is active
    socks5_proxy()    — return yt-dlp/requests proxy dict for the local SOCKS5 port

Root cause of the original DNS kill bug (2026-07-16):
    Mullvad's relay switching kills system DNS for 2-5s while rerouting.
    Spotify auth token refresh calls socket.getaddrinfo() during that window
    → socket.gaierror.  Fix lives in pipeline.auth._retry_network(), not

Defines: MullvadError, RelayInfo, _run, _parse_relay_info, status, is_connected, ensure_sweden, allow_lan, socks5_proxy, disconnect, wait_for_socks5, connect_relay, detect_version, apply_obfuscation, __str__

---

## Semantic links

→ [[pipeline-vpn-mullvad]]
→ [[pipeline-auth]]
→ [[2026-07-16-liked-songs-mullvad-multi-source-pipeline]]
→ [[scripts-run]]
→ [[pipeline-vpn-egress]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-scripts-run-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-auth-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-auth-md]]
→ [[cursor-ingest/2026-08-04-072347-config-config-yaml]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-vpn-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
