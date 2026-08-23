# phi / core / spotify_importer.py

#source #python

> path: phi/core/spotify_importer.py  
> ext: .py  

---

# phi / core / spotify_importer.py

phi.core.spotify_importer — import original Spotify playlists into phi.

Reads the downloaded Spotify library layout:

    <spotify_root>/
        library.json                    ← playlist metadata index
        Playlists/
            <spotify_playlist_id>/      ← one dir per downloaded playlist
                Artist - Title.mp3
                Artist - Title.json
                …

Each ``<spotify_playlist_id>/`` directory is matched to its human-readable
name and owner via ``library.json``, then upserted into ``PlaylistStore`` so
the original Spotify playlist structure is preserved inside 

Defines: ImportResult, _load_library_index, _collect_audio_paths, import_spotify_playlists, main, total, summary

---

## Semantic links

→ [[fetcher]]
→ [[index]]
→ [[mcp-server]]
→ [[obsidian-exporter]]
→ [[pipeline-sources-youtube-music]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-core-playlist-store-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-library-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-mcp-server-md]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-fetcher-md]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-cursor-skills-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
