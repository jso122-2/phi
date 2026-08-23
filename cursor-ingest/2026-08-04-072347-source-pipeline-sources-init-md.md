# source / pipeline-sources-init.md

#doc #md

> path: source/pipeline-sources-init.md  
> ext: .md  

---

# pipeline/sources/__init__

#code #module #pipeline #code

> source_path: pipeline/sources/__init__.py  
> package: pipeline  
> module: pipeline/sources/__init__  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/sources/__init__`  
**Source:** `pipeline/sources/__init__.py`

pipeline.sources — pluggable download backends.

All sources search for a track by title + artists and download via yt-dlp.
None of them pass Spotify URLs to yt-dlp, which would trigger yt-dlp's
Spotify extractor and return only the 30-second preview_url.

Priority order (matches config.yaml sources.priority):
    1. youtube_music   — ytmsearch: (YouTube Music catalogue)
    2. youtube         — ytsearch:  (regular YouTube, "official audio" bias)
    3. soundcloud      — scsearch:
    4. internet_archive — archive.org audio search

## Internal imports

`pipeline.sources.base`, `pipeline.sources.youtube_music`, `pipeline.sources.youtube`, `pipeline.sources.soundcloud`, `pipeline.sources.internet_archive`

---

## Semantic links

→ [[fetcher]]
→ [[index]]
→ [[indexer]]
→ [[mcp-server]]
→ [[obsidian-exporter]]

## Related notes

→ [[source/pipeline-sources-youtube-music]]
→ [[source/pipeline-fetcher-models]]
→ [[source/pipeline-sources-soundcloud]]
→ [[source/pipeline-fetcher-init]]
→ [[source/pipeline-sources-internet-archive]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[pipeline-sources-youtube]]
→ [[pipeline-sources-youtube-music]]
→ [[pipeline-fetcher-models]]
→ [[pipeline-fetcher-init]]
→ [[pipeline-index]]
→ [[pipeline-sources-base]]

---

## Semantic links

→ [[pipeline-bridge-init]]
→ [[pipeline-fetcher-init]]
→ [[pipeline-utils-config]]
→ [[pipeline-worker-init]]
→ [[pipeline-sources-base]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-fetcher-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-bridge-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-utils-config-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-vpn-init-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
