# source / pipeline-sources-internet-archive.md

#doc #md

> path: source/pipeline-sources-internet-archive.md  
> ext: .md  

---

# pipeline/sources/internet_archive

#code #module #pipeline #code

> source_path: pipeline/sources/internet_archive.py  
> package: pipeline  
> module: pipeline/sources/internet_archive  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/sources/internet_archive`  
**Source:** `pipeline/sources/internet_archive.py`

pipeline.sources.internet_archive — Internet Archive fallback source.

Searches the Internet Archive (archive.org) for audio recordings.
Useful as a last resort for very old or obscure tracks.

yt-dlp's internetarchive extractor requires a search URL format:
    https://archive.org/search?query=...&and[]=mediatype:audio

## API

- `class InternetArchiveSource` — Download from Internet Archive (last-resort fallback).

## Internal imports

`pipeline.fetcher.models`, `pipeline.sources.base`, `pipeline.sources.youtube_music`

---

## Semantic links

→ [[indexer]]
→ [[fetcher]]
→ [[index]]
→ [[2025-05-20-052550-operator-scraping-prompts]]
→ [[keep]]

## Related notes

→ [[source/pipeline-sources-soundcloud]]
→ [[source/pipeline-sources-youtube]]
→ [[source/pipeline-fetcher-models]]
→ [[source/pipeline-sources-init]]
→ [[source/pipeline-sources-youtube-music]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[pipeline-sources-init]]
→ [[pipeline-index]]
→ [[pipeline-sources-base]]
→ [[pipeline-sources-youtube]]
→ [[pipeline-fetcher-init]]
→ [[pipeline-sources-soundcloud]]

---

## Semantic links

→ [[pipeline-sources-internet-archive]]
→ [[pipeline-sources-base]]
→ [[pipeline-sources-youtube]]
→ [[pipeline-sources-soundcloud]]
→ [[pipeline-fetcher-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-base-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-fetcher-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-utils-config-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-soundcloud-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
