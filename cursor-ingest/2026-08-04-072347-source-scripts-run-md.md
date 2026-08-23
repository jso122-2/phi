# source / scripts-run.md

#doc #md

> path: source/scripts-run.md  
> ext: .md  

---

# scripts/run

#code #module #scripts #code

> source_path: scripts/run.py  
> package: scripts  
> module: scripts/run  
> hub: CODE  
> created_ts:   

---

**Package:** `scripts`  
**Module:** `scripts/run`  
**Source:** `scripts/run.py`

run.py — spotify-pipeline entry point.

Usage
-----
    python run.py                  # full run: VPN + fetch + download
    python run.py --no-vpn         # skip Mullvad setup (dev / CI)
    python run.py --config path/to/config.yaml

VPN sequence (when enabled)
----------------------------
    _setup_vpn(cfg)       connect to Mullvad Sweden, allow LAN
    _wait_for_dns(cfg)    wait until DNS resolves (2-5s window after relay switch)
    run_workers(...)      parallel downloads via yt-dlp through SOCKS5 proxy

## API

- `def _setup_vpn` — Connect to Mullvad Sweden and enable LAN.
- `def _wait_for_dns` — Block until the warmup host is DNS-resolvable and TCP-reachable, or raise TimeoutError.
- `def _worker_kwargs` — Build the kwargs dict injected into each worker / yt-dlp call.
- `def _parse_args`
- `def main`

## Internal imports

`pipeline.utils.config`, `pipeline.vpn.mullvad`, `pipeline.worker`, `pipeline.sources`, `pipeline.sources.soundcloud`, `pipeline.sources.internet_archive`, `pipeline.sources.youtube_music`, `pipeline.sources.youtube`

---

## Semantic links

→ [[config]]
→ [[2026-07-16-liked-songs-mullvad-multi-source-pipeline]]
→ [[auth]]
→ [[index]]
→ [[mcp-server]]

## Related notes

→ [[source/pipeline-vpn-mullvad]]
→ [[source/pipeline-fetcher-init]]
→ [[source/pipeline-vpn-manager]]
→ [[source/mcp-server-server]]
→ [[source/pipeline-auth]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[pipeline-vpn-mullvad]]
→ [[pipeline-auth]]
→ [[pipeline-vpn-init]]
→ [[pipeline-fetcher-init]]
→ [[pipeline-worker-init]]
→ [[pipeline-vpn-manager]]

---

## Semantic links

→ [[scripts-run]]
→ [[pipeline-fetcher-init]]
→ [[index]]
→ [[pipeline-fetcher-models]]
→ [[config]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-scripts-run-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-init-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-config-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-fetcher-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-server-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
