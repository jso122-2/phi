# phi / core / playlist_store.py

#source #python

> path: phi/core/playlist_store.py  
> ext: .py  

---

# phi / core / playlist_store.py

phi.core.playlist_store — named playlist persistence (SQLite).

Schema (written into ~/.phi/meta.db alongside the metadata cache):

    playlists (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    UNIQUE NOT NULL,
        created_at  REAL    NOT NULL,
        updated_at  REAL    NOT NULL,
        spotify_id  TEXT    UNIQUE,          -- Spotify playlist ID, NULL for local playlists
        owner       TEXT,                    -- Spotify owner username
    )

    playlist_tracks (
        playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
 

Defines: PlaylistInfo, SpotifyPlaylistInfo, PlaylistStore, __init__, _init_schema, _migrate_schema, create, rename, delete, all, get, by_spotify_id, all_spotify, tracks, add_track, add_tracks, remove_track, create_from_paths, upsert_spotify_playlist, close

---

## Semantic links

→ [[indexer]]
→ [[mcp-server]]
→ [[fetcher]]
→ [[index]]
→ [[cursor-skills]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-core-spotify-importer-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-cursor-skills-md]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-indexer-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-library-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-mcp-server-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
