# source / pipeline-sources-soundcloud.md

#doc #md

> path: source/pipeline-sources-soundcloud.md  
> ext: .md  

---

# pipeline/sources/soundcloud

#code #module #pipeline #code

> source_path: pipeline/sources/soundcloud.py  
> package: pipeline  
> module: pipeline/sources/soundcloud  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/sources/soundcloud`  
**Source:** `pipeline/sources/soundcloud.py`

pipeline.sources.soundcloud — SoundCloud fallback source.

Searches SoundCloud via yt-dlp's scsearch: extractor.  Useful for
tracks that are unavailable on YouTube Music / YouTube (regional blocks,
copyright takedowns, etc.).

Note: config.yaml sets soundcloud.use_proxy=false because SoundCloud
blocks SOCKS5 in some regions.  The proxy arg is accepted but defaults
to None here to honour that setting at the call site.

## API

- `class SoundCloudSource` — Download from SoundCloud by searching title + artists.

## Internal imports

`pipeline.fetcher.models`, `pipeline.sources.base`, `pipeline.sources.youtube_music`

---

## Semantic links

→ [[index]]
→ [[fetcher]]
→ [[indexer]]
→ [[obsidian-exporter]]
→ [[scheduler]]

## Related notes

→ [[source/pipeline-sources-youtube]]
→ [[source/pipeline-sources-internet-archive]]
→ [[source/pipeline-fetcher-models]]
→ [[source/pipeline-sources-youtube-music]]
→ [[source/pipeline-sources-init]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[pipeline-sources-init]]
→ [[pipeline-sources-youtube]]
→ [[pipeline-index]]
→ [[pipeline-fetcher-models]]
→ [[pipeline-fetcher-init]]
→ [[pipeline-sources-base]]

---

## Semantic links

→ [[pipeline-sources-soundcloud]]
→ [[pipeline-fetcher-models]]
→ [[pipeline-sources-youtube-music]]
→ [[pipeline-sources-internet-archive]]
→ [[pipeline-sources-youtube]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-soundcloud-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-internet-archive-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-youtube-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-internet-archive-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
