# phi / meta / track_store.py

#source #python

> path: phi/meta/track_store.py  
> ext: .py  

---

# phi / meta / track_store.py

phi.meta.track_store — per-track local data store.

Materialises a self-contained directory for every track in the phi library:

    ~/.phi/library/
        _index.json                  # slug ↔ original-path index
        radiohead_creep/
            audio.mp3                # symlink → original file
            meta.json                # file tags (title, artist, album, year…)
            annotations.json         # all enrichment (Spotify, LFM, MB, Discogs, Deezer…)
            features.json            # librosa audio features (BPM, MFCCs, spectral…)
            telemetry.json           # pl

Defines: build_track_dir, _compute_spectrograms, TrackStore, main, __init__, build_all, build_one, refresh_telemetry, prune, _do

---

## Semantic links

→ [[pipeline-fetcher-models]]
→ [[indexer]]
→ [[scripts-embed-tracks]]
→ [[fetcher]]
→ [[index]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-library-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-loader-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-spotify-importer-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-track-index-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-indexer-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
