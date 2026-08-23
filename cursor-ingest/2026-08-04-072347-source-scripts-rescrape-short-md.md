# source / scripts-rescrape-short.md

#doc #md

> path: source/scripts-rescrape-short.md  
> ext: .md  

---

# scripts/rescrape_short

#code #module #scripts #code

> source_path: scripts/rescrape_short.py  
> package: scripts  
> module: scripts/rescrape_short  
> hub: CODE  
> created_ts:   

---

**Package:** `scripts`  
**Module:** `scripts/rescrape_short`  
**Source:** `scripts/rescrape_short.py`

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
Spotify's Web API preview_url clips are always 29.5–30.5 seconds.
This script targets the range 28.5–31.0s to capture the whole cluster
while leaving genuinely short tracks (intros, skits < 28s) untouched.

## API

- `def _duration` — Return audio duration in seconds via mutagen, or None on failure.
- `def _read_tags` — Return basic tag dict (title, artist, album) from an audio file.
- `def _make_track_info` — Build a TrackInfo from a file's tags.  Returns None if no title/artist.
- `def _find_phi_library` — Load all track paths from ~/.phi/state.json.
- `def _scan_dir` — Return all audio files under *directory*.
- `def _find_short_tracks` — Return (path, duration) for tracks in the Spotify preview range.
- `def _rescrape_one` — Re-download one track and overwrite the original file.
- `def rescrape` — Find and re-download all ~30s preview tracks in *paths*.
- `def main`

## Internal imports

`pipeline.fetcher.models`, `pipeline.sources`, `pipeline.worker.multi_source`

---

## Semantic links

→ [[2026-07-21-000947-clean-the-entire-misc-folder-top-to-bottom]]
→ [[index]]
→ [[indexer]]
→ [[worker]]
→ [[fetcher]]

## Relate

---

## Semantic links

→ [[scripts-rescrape-short]]
→ [[scripts-embed-tracks]]
→ [[pipeline-sources-internet-archive]]
→ [[pipeline-sources-soundcloud]]
→ [[tools-enrich-c7]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-scripts-rescrape-short-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-embed-tracks-md]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-soundcloud-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-internet-archive-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
