# config / config.yaml

#doc #yaml

> path: config/config.yaml  
> ext: .yaml  

---

# spotify-pipeline configuration
# Credentials go in .env, never here.

download:
  output_dir: ~/Desktop/Spotify
  intermediate_format: mp3
  bitrate: "320k"
  chunk_size: 100         # tracks per spotdl/yt-dlp job

obsidian:
  vault_path: ~/Documents/Spotify-Rip/Spotify-rip
  subdir: spotify

playlists:
  owned_only: true        # skip playlists the user follows but doesn't own

# ── VPN (Mullvad) ─────────────────────────────────────────────────────────────
vpn:
  enabled: true
  country: sweden         # relay location passed to 'mullvad relay set location'
  connect_timeout_s: 30   # seconds to wait for Mullvad to report Connected
  allow_lan: true         # run 'mullvad lan set allow' after connecting

  # DNS warmup gate — poll this host until it resolves before starting workers.
  # Prevents socket.gaierror during the 2-5s DNS blackout on relay switching.
  dns_warmup_host: "open.spotify.com"
  dns_warmup_timeout_s: 60
  dns_warmup_interval_s: 1

  socks5:
    host: "127.0.0.1"
    port: 1080            # Mullvad's local SOCKS5 proxy port

  # ── Defensive VPN (VPNManager) ──────────────────────────────────────────────
  # relay_pool: EU relay pool for rotation. Countries: se (primary), nl, de.
  # To override with a custom list set relay_pool.relays to an explicit list.
  relay_pool:
    countries: [se, nl, de]   # EU pool; SE = primary (best YouTube Music coverage)
    history_size: 2           # exclude last N relays from next pick
    auto_refresh: false       # set true to repopulate from `mullvad relay list` at startup

  # egress verification — multi-endpoint consensus (requires 2/3 agreement)
  egress:
    timeout_s: 12
    endpoints:
      - "https://am.i.mullvad.net/json"   # Mullvad's own — confirms mullvad_exit_ip
      - "https://icanhazip.com"           # neutral bare-IP
      - "https://api.ipify.org?format=json"  # neutral JSON

  # obfuscation — applied automatically on connect based on mullvad version
  # (2023+): obfuscation auto (Shadowso

---

## Semantic links

→ [[2026-07-16-liked-songs-mullvad-multi-source-pipeline]]
→ [[pipeline-vpn-mullvad]]
→ [[scripts-run]]
→ [[config]]
→ [[auth]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-scripts-run-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-config-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-vpn-mullvad-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-youtube-music-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-run-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
