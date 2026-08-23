# scripts / rescrape_short.py

#source #python

> path: scripts/rescrape_short.py  
> ext: .py  

---

# scripts / rescrape_short.py

scripts/rescrape_short.py — re-download tracks that are ~30s Spotify previews.

Usage
-----
    # Dry-run: list what would be rescrapped
    python scripts/rescrape_short.py --dry-run

    # Live rescrape with default 4 workers
    python scripts/rescrape_short.py

    # Faster / slower
    python scripts/rescrape_short.py --workers 2

    # Without VPN proxy
    python scripts/rescrape_short.py --no-proxy

    # Scan a specific directory instead of the phi library
    python scripts/rescrape_short.py --scan ~/Desktop/Spotify

Detection logic
---------------
Spotify's Web API preview_url clips

Defines: _duration, _read_tags, _make_track_info, _find_phi_library, _scan_dir, _find_short_tracks, _rescrape_one, rescrape, main

---

## Semantic links

→ [[scripts-rescrape-short]]
→ [[scripts-run]]
→ [[pipeline-sources-init]]
→ [[pipeline-fetcher-models]]
→ [[index]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-scripts-rescrape-short-md]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-run-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-run-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-init-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
