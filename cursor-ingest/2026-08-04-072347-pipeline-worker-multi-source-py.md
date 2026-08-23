# pipeline / worker / multi_source.py

#source #python

> path: pipeline/worker/multi_source.py  
> ext: .py  

---

# pipeline / worker / multi_source.py

pipeline.worker.multi_source — per-track source priority chain.

For each track, tries sources in config priority order until one
succeeds.  Source objects are passed in so the caller controls ordering
and proxy settings per source.

Usage
-----
    from pipeline.worker.multi_source import download_track
    from pipeline.sources import DEFAULT_SOURCES

    result = download_track(
        track,
        output_dir=Path("~/Desktop/Spotify/Liked Songs"),
        fmt="mp3",
        sources=DEFAULT_SOURCES,
        proxy="socks5://127.0.0.1:1080",
        timeout_s=600,
    )
    if result.ok:
  

Defines: download_track

---

## Semantic links

→ [[pipeline-worker-multi-source]]
→ [[pipeline-worker-executor]]
→ [[pipeline-fetcher-models]]
→ [[pipeline-sources-init]]
→ [[pipeline-sources-youtube-music]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-multi-source-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-fetcher-models-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-init-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-worker-executor-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-fetcher-models-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
