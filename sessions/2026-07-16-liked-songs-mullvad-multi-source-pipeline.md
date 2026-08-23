# Session: 2026-07-16 — Liked Songs, Mullvad VPN, Multi-Source Pipeline

#session 

**Prompt:** Get liked songs downloading. Fix spotapi error on playlist fetch. Set up proper architecture with mmap pipe, proper workers, Swedish VPN routing.

**Thinking:** The original spotapi error (playlist fetch failing at get_session() → DNS/HTTP failure hitting open.spotify.com) was from spotdl's internal Spotify scraping layer, which is brittle. The fix was to switch fully to yt-dlp with multi-source fallback. The Mullvad VPN caused a secondary issue: DNS was killed system-wide during relay switching, which caused the Spotify auth token refresh to fail with socket.gaierror. Fixed with retry logic + DNS warmup gate.

**Outcome:**
- Built pipeline/bridge/mmap_pipe.py — anonymous mmap ring buffer (header + slots, Condition-based sync)
- Built pipeline/bridge/coordinator.py — dispatch + complete daemon threads bridging SQLite ↔ pipes
- Built pipeline/vpn/mullvad.py — Mullvad CLI wrapper, ensure_sweden(), socks5_proxy(), allow_lan()
- Built pipeline/sources/ — 4 backends: youtube_music, youtube, soundcloud, internet_archive
- Built pipeline/worker/multi_source.py — source priority chain per track
- Built pipeline/worker/fs_organizer.py — staging → output with M3U updates
- Updated pipeline/worker/executor.py — full 3-phase shutdown, mmap pipeline
- Fixed pipeline/auth.py — _retry_network() wrapper (6 × 5s) for DNS transients
- Fixed run.py — _setup_vpn(), _wait_for_dns(), _worker_kwargs() helpers
- Added vpn / sources / workers sections to config/config.yaml
- Cleared 616 cache-chunk jobs from queue
- Confirmed Mullvad connected: se-sto-wg-204, Stockholm (89.37.63.206)

## Graph links discovered

→ [[environment]]  
→ [[workers]]  
→ [[CODE]]  
→ [[mcp-server]]  
→ [[temporal-index]]  
→ [[2026-07-15]]

---

## Auto-linked

→ [[config]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[scheduler]]
→ [[worker]]
→ [[indexer]]

→ [[queue]]
→ [[cursor-skills]]
→ [[fetcher]]
→ [[obsidian-exporter]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[auth]]

→ [[2026-07-15-spotify-pipeline-mcp-cache-queue]]
→ [[sessions]]
→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]
→ [[git-log]]
→ [[graph]]
→ [[2026-07-13-095004-cairrnify-the-mcp-server-fix-dom-queue-open]]

→ [[pipeline-index]]
→ [[pipeline-auth]]
→ [[scripts-run]]
→ [[pipeline-vpn-mullvad]]
→ [[pipeline-worker-init]]
→ [[pipeline-vpn-init]]
