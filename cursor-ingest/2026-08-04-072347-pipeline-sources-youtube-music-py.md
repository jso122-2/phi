# pipeline / sources / youtube_music.py

#source #python

> path: pipeline/sources/youtube_music.py  
> ext: .py  

---

# pipeline / sources / youtube_music.py

pipeline.sources.youtube_music — YouTube Music download source.

THE FIX FOR 30-SECOND SONGS
============================
yt-dlp's built-in Spotify extractor fetches the track's `preview_url`
from Spotify's Web API — a 30-second MP3 clip.  Full tracks are
DRM-encrypted and cannot be obtained via the Spotify API.

This source deliberately does NOT pass Spotify URLs to yt-dlp.
Instead it:

    1. Builds a search query from the track's title + artists
       e.g.  "Radiohead - Creep"
    2. Uses yt-dlp's ytmsearch: prefix to search YouTube Music
       → finds the full-length music video / audio 

Defines: _find_downloaded_file, YouTubeMusicSource, download

---

## Semantic links

→ [[pipeline-sources-youtube-music]]
→ [[pipeline-sources-init]]
→ [[pipeline-sources-youtube]]
→ [[pipeline-sources-soundcloud]]
→ [[fetcher]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-youtube-music-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-fetcher-models-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-youtube-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
