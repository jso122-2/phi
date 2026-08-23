# pipeline / sources / __init__.py

#source #python

> path: pipeline/sources/__init__.py  
> ext: .py  

---

# pipeline / sources / __init__.py

pipeline.sources — pluggable download backends.

All sources search for a track by title + artists and download via yt-dlp.
None of them pass Spotify URLs to yt-dlp, which would trigger yt-dlp's
Spotify extractor and return only the 30-second preview_url.

Priority order (matches config.yaml sources.priority):
    1. youtube_music   — ytmsearch: (YouTube Music catalogue)
    2. youtube         — ytsearch:  (regular YouTube, "official audio" bias)
    3. soundcloud      — scsearch:
    4. internet_archive — archive.org audio search

---

## Semantic links

→ [[pipeline-sources-init]]
→ [[pipeline-sources-youtube-music]]
→ [[pipeline-sources-soundcloud]]
→ [[pipeline-sources-youtube]]
→ [[pipeline-fetcher-models]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-youtube-music-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-fetcher-models-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-youtube-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-youtube-music-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
