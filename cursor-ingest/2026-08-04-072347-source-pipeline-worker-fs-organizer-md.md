# source / pipeline-worker-fs-organizer.md

#doc #md

> path: source/pipeline-worker-fs-organizer.md  
> ext: .md  

---

# pipeline/worker/fs_organizer

#code #module #pipeline #code

> source_path: pipeline/worker/fs_organizer.py  
> package: pipeline  
> module: pipeline/worker/fs_organizer  
> hub: CODE  
> created_ts:   

---

**Package:** `pipeline`  
**Module:** `pipeline/worker/fs_organizer`  
**Source:** `pipeline/worker/fs_organizer.py`

pipeline.worker.fs_organizer — staging → output file organizer with M3U updates.

Responsibility
--------------
After a source downloads a track into the staging directory, FsOrganizer:

    1. Resolves the final destination path (output_dir / safe_filename.ext)
    2. Handles collisions with an integer suffix  (e.g. "Title (2).mp3")
    3. Moves the file atomically (same filesystem) or falls back to copy+delete
    4. Appends an #EXTINF entry to the M3U playlist for the destination directory
       (creates the M3U if it doesn't exist)

M3U format
----------
    #EXTM3U
    #EXTINF:<duration_ms_as_int>,<artists> - <title>
    /absolute/path/to/Artist - Title.mp3

Duration is taken from TrackInfo.duration_ms when available; falls back to -1
(unknown) which is valid per the M3U spec.

Usage
-----
    organizer = FsOrganizer(output_dir=Path("~/Desktop/Spotify/Liked Songs"),
                             staging_dir=Path("data/staging"),
                             m3u_path=Path("~/Desktop/Spotify/liked.m3u"))

    final_path = organizer.organize(result)
    # result.path → staging file moved to output_dir
    # liked.m3u  → new #EXTINF line appended

If staging_dir is None, the source already wrote directly to output_dir and
the move step is skipped — only the M3U is updated.

If m3u_path is None, the playlist update step is skipped.

## API

- `class FsOrganizer` — Move downloaded files from staging to output and maintain an M3U playlist.
- `def _unique_dest` — Return a path that does not exist, appending ` (N)` before the suffix

## Internal imports

`pipeline.sources.base`

---

## Semantic links

→ [[worker]]
→ [[index]]
→ [[scheduler]]
→ [

---

## Semantic links

→ [[pipeline-worker-fs-organizer]]
→ [[pipeline-worker-init]]
→ [[workers-base]]
→ [[pipeline-worker-multi-source]]
→ [[pipeline-fetcher-models]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-pipeline-worker-fs-organizer-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-multi-source-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-utils-config-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-base-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
