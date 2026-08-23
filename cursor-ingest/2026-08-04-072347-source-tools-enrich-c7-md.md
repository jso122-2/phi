# source / tools-enrich-c7.md

#doc #md

> path: source/tools-enrich-c7.md  
> ext: .md  

---

# tools/enrich_c7

#code #module #tools #code

> source_path: tools/enrich_c7.py  
> package: tools  
> module: tools/enrich_c7  
> hub: CODE  
> created_ts:   

---

**Package:** `tools`  
**Module:** `tools/enrich_c7`  
**Source:** `tools/enrich_c7.py`

tools.enrich_c7 — targeted metadata enrichment for cluster-7 gaps.

Two gap types
-------------
A. Named tracks with sparse/missing lfm_tags (9 tracks)
   → Hits Last.fm track.getInfo + artist.getTopTags fallback
   → Requires: LASTFM_API_KEY env var (or --lfm-key arg)

B. Stem-only tracks with no artist/name (26 tracks, YouTube IDs)
   → AcoustID fingerprint via fpcalc → MusicBrainz lookup → identity
   → Requires: fpcalc on PATH (brew install chromaprint) + ACOUSTID_KEY env

Run
---
    # Named tracks (Last.fm):
    LASTFM_API_KEY=<your_key> python -m tools.enrich_c7

    # Stem-only (AcoustID):
    ACOUSTID_KEY=<your_key> python -m tools.enrich_c7 --mode acoustid

    # Both:
    LASTFM_API_KEY=<key> ACOUSTID_KEY=<key> python -m tools.enrich_c7 --mode all

    # Dry run — show what would be patched, no writes:
    python -m tools.enrich_c7 --dry-run

## API

- `def _api_get`
- `def _strip_html`
- `def _identify_gaps` — Return (named_sparse, stem_only) lists from the library.
- `def _lfm_track_info`
- `def _lfm_artist_tags`
- `def enrich_named`
- `def _fpcalc_bin`
- `def _fpcalc` — Run fpcalc and return (duration_int, fingerprint) or None.
- `def _acoustid_lookup` — POST to AcoustID — fingerprints are too long for GET URLs.
- `def _yt_oembed` — Fetch YouTube oEmbed for a video ID — no API key required.
- `def _parse_yt_title` — Best-effort parse of 'Artist - Track Title' from a YouTube title.
- `def enrich_stems` — Identify stem-only (YouTube ID) tracks via:
- `def _print_report`
- `def main`

---

## Semantic links

→ [[fetcher]]
→ [[indexer]]
→ [[index]]
→ [[index]]
→ [[scratch]]

## Related notes

→ [[source/models-metadata-cluster]]
→ [[source/models-genre-predictor]]
→ [[source/scripts-embed-tracks]]
→ [[sou

---

## Semantic links

→ [[tools-enrich-c7]]
→ [[models-metadata-cluster]]
→ [[tools-ingest]]
→ [[tools-cursor-ingest]]
→ [[source]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tools-enrich-c7-py]]
→ [[cursor-ingest/2026-08-04-072347-source-models-metadata-cluster-md]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-ingest-md]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-embed-tracks-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
