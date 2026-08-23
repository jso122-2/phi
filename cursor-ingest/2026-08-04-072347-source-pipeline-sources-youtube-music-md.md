# source / pipeline-sources-youtube-music.md

#doc #md

> path: source/pipeline-sources-youtube-music.md  
> ext: .md  

---

# pipeline/sources/youtube_music

#code #module #pipeline #code

> source_path: pipeline/sources/youtube_music.py  
> package: pipeline  
> module: pipeline/sources/youtube_music  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/sources/youtube_music`  
**Source:** `pipeline/sources/youtube_music.py`

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
       → finds the full-length music video / audio track
    3. Downloads and post-processes to the target format

The result is a full-length file, not a preview clip.

## API

- `def _find_downloaded_file` — Locate the file yt-dlp wrote into *output_dir*.
- `class YouTubeMusicSource` — Download from YouTube Music by searching title + artists.

## Internal imports

`pipeline.fetcher.models`, `pipeline.sources.base`

---

## Semantic links

→ [[fetcher]]
→ [[index]]
→ [[2026-07-16-liked-songs-mullvad-multi-source-pipeline]]
→ [[obsidian-exporter]]
→ [[scheduler]]

## Related notes

→ [[source/pipeline-sources-init]]
→ [[source/pipeline-sources-youtube]]
→ [[source/pipeline-fetcher-models]]
→ [[source/pipeline-sources-soundcloud]]
→ [[source/pipeline-fetcher-init]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[pipeline-sources-init]]
→ [[pipeline-sources-youtube]]
→ [[pipeline-fetcher-models]]
→ [[pipeline-fetcher-init]]
→ [[pipeline-sources-soundcloud]]
→ [[pipeline-index]]

---

## Semantic links

→ [[pipeline-sources-youtube-music]]
→ [[pipeline-sources-youtube]]
→ [[pipeline-sources-soundcloud]]
→ [[pipeline-sources-init]]
→ [[pipeline-sources-internet-archive]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-youtube-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-youtube-music-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-init-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-youtube-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-soundcloud-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
