# source / pipeline-worker-multi-source.md

#doc #md

> path: source/pipeline-worker-multi-source.md  
> ext: .md  

---

# pipeline/worker/multi_source

#code #module #pipeline #code

> source_path: pipeline/worker/multi_source.py  
> package: pipeline  
> module: pipeline/worker/multi_source  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/worker/multi_source`  
**Source:** `pipeline/worker/multi_source.py`

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
        print("saved to", result.path)
    else:
        print("all sources failed:", result.error)

## API

- `def download_track` — Try each source in *sources* order.  Return on first success.

## Internal imports

`pipeline.fetcher.models`, `pipeline.sources.base`

---

## Semantic links

→ [[worker]]
→ [[index]]
→ [[scheduler]]
→ [[2025-08-28-121214-2025-08-28t22-12-14-433-10-00]]
→ [[queue]]

## Related notes

→ [[source/pipeline-worker-executor]]
→ [[source/pipeline-worker-init]]
→ [[source/pipeline-sources-base]]
→ [[source/pipeline-fetcher-models]]
→ [[source/pipeline-worker-fs-organizer]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[pipeline-worker-init]]
→ [[pipeline-sources-base]]
→ [[pipeline-fetcher-init]]
→ [[pipeline-index]]
→ [[pipeline-worker-executor]]
→ [[pipeline-bridge-init]]

---

## Semantic links

→ [[pipeline-worker-multi-source]]
→ [[pipeline-worker-init]]
→ [[pipeline-worker-executor]]
→ [[pipeline-sources-base]]
→ [[workers-cairrn-worker]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-init-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-worker-multi-source-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-executor-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-utils-config-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
