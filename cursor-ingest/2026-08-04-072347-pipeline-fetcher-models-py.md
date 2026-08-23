# pipeline / fetcher / models.py

#source #python

> path: pipeline/fetcher/models.py  
> ext: .py  

---

# pipeline / fetcher / models.py

pipeline.fetcher.models — core data models for the download pipeline.

TrackInfo  — one Spotify track (name, artists, album, url, duration)
Job        — a batch of tracks destined for one output directory

Design note
-----------
Workers receive TrackInfo objects, not raw Spotify URLs.  The sources/
layer searches YouTube Music (or fallback sources) by title + artist,
which avoids yt-dlp's Spotify extractor — that extractor only returns
the 30-second preview_url from Spotify's Web API, not the full track.


Defines: TrackInfo, Job, search_query, safe_filename, _clean

---

## Semantic links

→ [[pipeline-fetcher-models]]
→ [[fetcher]]
→ [[pipeline-sources-youtube-music]]
→ [[pipeline-sources-init]]
→ [[index]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-init-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-fetcher-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-fetcher-models-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-fetcher-init-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-youtube-music-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
