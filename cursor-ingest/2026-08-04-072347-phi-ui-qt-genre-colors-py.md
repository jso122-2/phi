# phi / ui / qt / genre_colors.py

#source #python

> path: phi/ui/qt/genre_colors.py  
> ext: .py  

---

# phi / ui / qt / genre_colors.py

phi.ui.qt.genre_colors — deterministic genre → colour palette.

Used by PlaylistWidget and QueueRoom to paint per-track genre indicator dots.

Public API
----------
    GENRE_PALETTE          : list[str]   — 20 hex colours, dark-theme readable
    genre_color(genre)     : str         — deterministic colour for any genre string
    genres_from_meta(meta, ann) : list[str] — parsed genres from meta/annotation dicts
    primary_color(path, library)  : str  — first-genre colour for a track path
    build_genre_map(paths, library) -> dict[str, str]
                           — build {path: hex_color

Defines: _norm, genres_from_meta, genre_color, primary_color, build_genre_map, active_genres, _add

---

## Semantic links

→ [[models-genre-predictor]]
→ [[scripts-bake-ascii]]
→ [[engine-phi-player]]
→ [[GENRE]]
→ [[scripts-embed-tracks]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-genre-renderer-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-genre-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-genre-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-genre-graph-utils-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-hyphal-library-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
