# source / pipeline-sources-youtube.md

#doc #md

> path: source/pipeline-sources-youtube.md  
> ext: .md  

---

# pipeline/sources/youtube

#code #module #pipeline #code

> source_path: pipeline/sources/youtube.py  
> package: pipeline  
> module: pipeline/sources/youtube  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/sources/youtube`  
**Source:** `pipeline/sources/youtube.py`

pipeline.sources.youtube — regular YouTube fallback source.

Searches YouTube (not YouTube Music) using ytsearch: when the YouTube
Music source fails or is unavailable.  Prefers "official audio" and
"lyrics" videos over unofficial covers.

## API

- `class YouTubeSource` — Download from regular YouTube by searching title + artists.

## Internal imports

`pipeline.fetcher.models`, `pipeline.sources.base`, `pipeline.sources.youtube_music`

---

## Semantic links

→ [[index]]
→ [[fetcher]]
→ [[indexer]]
→ [[2025-05-20-052550-operator-scraping-prompts]]
→ [[scheduler]]

## Related notes

→ [[source/pipeline-sources-soundcloud]]
→ [[source/pipeline-sources-internet-archive]]
→ [[source/pipeline-sources-youtube-music]]
→ [[source/pipeline-fetcher-models]]
→ [[source/pipeline-sources-init]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[pipeline-sources-init]]
→ [[pipeline-sources-youtube-music]]
→ [[pipeline-fetcher-models]]
→ [[pipeline-index]]
→ [[pipeline-sources-base]]
→ [[pipeline-sources-soundcloud]]

---

## Semantic links

→ [[pipeline-sources-youtube]]
→ [[pipeline-sources-youtube-music]]
→ [[pipeline-sources-soundcloud]]
→ [[pipeline-sources-internet-archive]]
→ [[pipeline-sources-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-youtube-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-youtube-music-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-init-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-soundcloud-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-soundcloud-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
