# phi / meta / spotify_bulk_enrich.py

#source #python

> path: phi/meta/spotify_bulk_enrich.py  
> ext: .py  

---

# phi / meta / spotify_bulk_enrich.py

phi.meta.spotify_bulk_enrich — batch Spotify enrichment for the phi library.

Iterates every track that has never been attempted for Spotify enrichment
(spotify_enriched is NULL in annotations) and enriches it using:

  1. ISRC exact-match lookup  (if isrc is already stored in annotations)
  2. title + artist fuzzy search  (fallback)

Results are written directly to ~/.phi/meta.db annotations — no phi app
instance required.  Tracks with a previous attempt (spotify_enriched = True
or False) are skipped unless --retry-failed is passed.

Usage
-----
  python -m phi.meta.spotify_bulk_enrich       

Defines: SpotifyBulkResult, _get_annotation, _upsert_annotation, run_bulk_enrich, _main, __str__, _progress

---

## Semantic links

→ [[fetcher]]
→ [[pipeline-sources-youtube-music]]
→ [[indexer]]
→ [[pipeline-fetcher-models]]
→ [[tools-enrich-c7]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-library-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-enricher-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-track-store-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-fetcher-models-py]]
→ [[cursor-ingest/2026-08-04-072347-tools-enrich-c7-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
