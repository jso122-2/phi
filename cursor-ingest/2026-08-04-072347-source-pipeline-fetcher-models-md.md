# source / pipeline-fetcher-models.md

#doc #md

> path: source/pipeline-fetcher-models.md  
> ext: .md  

---

# pipeline/fetcher/models

#code #module #pipeline #code

> source_path: pipeline/fetcher/models.py  
> package: pipeline  
> module: pipeline/fetcher/models  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/fetcher/models`  
**Source:** `pipeline/fetcher/models.py`

pipeline.fetcher.models — core data models for the download pipeline.

TrackInfo  — one Spotify track (name, artists, album, url, duration)
Job        — a batch of tracks destined for one output directory

Design note
-----------
Workers receive TrackInfo objects, not raw Spotify URLs.  The sources/
layer searches YouTube Music (or fallback sources) by title + artist,
which avoids yt-dlp's Spotify extractor — that extractor only returns
the 30-second preview_url from Spotify's Web API, not the full track.

## API

- `class TrackInfo` — Metadata for one Spotify track, resolved before the download stage.
- `class Job` — A unit of work: a list of tracks to download into one output directory.

---

## Semantic links

→ [[index]]
→ [[fetcher]]
→ [[indexer]]
→ [[scheduler]]
→ [[mcp-server]]

## Related notes

→ [[source/pipeline-fetcher-init]]
→ [[source/pipeline-sources-youtube-music]]
→ [[source/pipeline-sources-init]]
→ [[source/pipeline-sources-youtube]]
→ [[source/pipeline-sources-soundcloud]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[pipeline-fetcher-init]]
→ [[pipeline-sources-base]]
→ [[pipeline-sources-init]]
→ [[pipeline-index]]
→ [[pipeline-sources-youtube-music]]
→ [[pipeline-worker-init]]

---

## Semantic links

→ [[pipeline-fetcher-models]]
→ [[fetcher]]
→ [[pipeline-fetcher-init]]
→ [[pipeline-sources-init]]
→ [[index]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-pipeline-fetcher-init-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-fetcher-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-fetcher-models-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-models-metadata-cluster-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
