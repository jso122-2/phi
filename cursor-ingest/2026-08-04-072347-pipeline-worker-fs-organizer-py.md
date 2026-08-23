# pipeline / worker / fs_organizer.py

#source #python

> path: pipeline/worker/fs_organizer.py  
> ext: .py  

---

# pipeline / worker / fs_organizer.py


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
    #EXTINF:<duration

Defines: FsOrganizer, _unique_dest, __init__, organize, update_m3u, _resolve_dest, _move

---

## Semantic links

→ [[pipeline-worker-fs-organizer]]
→ [[worker]]
→ [[pipeline-worker-executor]]
→ [[index]]
→ [[pipeline-fetcher-models]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-worker-fs-organizer-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-worker-multi-source-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-fetcher-models-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-scheduler-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-extract-worker-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
