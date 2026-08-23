# source / pipeline-vpn-mullvad.md

#doc #md

> path: source/pipeline-vpn-mullvad.md  
> ext: .md  

---

# pipeline/vpn/mullvad

#code #module #pipeline #code

> source_path: pipeline/vpn/mullvad.py  
> package: pipeline  
> module: pipeline/vpn/mullvad  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/vpn/mullvad`  
**Source:** `pipeline/vpn/mullvad.py`

pipeline.vpn.mullvad — Mullvad CLI wrapper for the spotify-pipeline.

Three public entry points used by run.py:
    ensure_sweden()   — connect to a Swedish relay; idempotent
    allow_lan()       — permit LAN traffic while VPN is active
    socks5_proxy()    — return yt-dlp/requests proxy dict for the local SOCKS5 port

Root cause of the original DNS kill bug (2026-07-16):
    Mullvad's relay switching kills system DNS for 2-5s while rerouting.
    Spotify auth token refresh calls socket.getaddrinfo() during that window
    → socket.gaierror.  Fix lives in pipeline.auth._retry_network(), not here.

## API

- `class MullvadError` — Raised when a Mullvad CLI call fails or times out.
- `class RelayInfo` — Snapshot of the active Mullvad relay.
- `def _run` — Run a mullvad subcommand, return CompletedProcess.
- `def _parse_relay_info` — Parse hostname, city, IP from status output like:
- `def status` — Return raw Mullvad status string (stdout + stderr).
- `def is_connected` — True if Mullvad reports 'Connected'.
- `def ensure_sweden` — Connect to a Swedish relay; return RelayInfo.  Idempotent — safe to call
- `def allow_lan` — Allow LAN traffic while the VPN tunnel is active.
- `def socks5_proxy` — Return a yt-dlp / requests -compatible SOCKS5 proxy dict.
- `def disconnect` — Disconnect Mullvad (best-effort — does not raise on failure).
- `def wait_for_socks5` — Poll until the local SOCKS5 port is reachable (indicates tunnel is live).
- `def connect_relay` — Connect to a specific Mullvad relay by hostname.
- `def detect_version` — Return the Mullvad version as an integer tuple, e.g. (2024, 3).
- `def apply_obfuscation` — Apply the strongest available obfuscation mode for the installed

---

## Semantic links

→ [[pipeline-vpn-mullvad]]
→ [[pipeline-vpn-init]]
→ [[pipeline-vpn-egress]]
→ [[scripts-run]]
→ [[pipeline-vpn-relay-pool]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-egress-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-manager-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-vpn-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-utils-config-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
