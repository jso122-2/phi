# phi / meta / enricher.py

#source #python

> path: phi/meta/enricher.py  
> ext: .py  

---

# phi / meta / enricher.py

phi.meta.enricher — per-track enrichment pipeline.

Coordinates fingerprinting → AcoustID lookup → MusicBrainz fetch →
tag merge → optional write-back.

EnrichResult carries everything the caller needs:
  - merged_meta   : dict ready for Library.store_meta()
  - annotation    : dict ready for Library.store_annotation()
  - review_item   : set when confidence was below threshold (user must confirm)
  - wrote_tags    : True if file tags were actually updated on disk


Defines: EnrichResult, _write_tags, _write_composer, _write_art, enrich_track

---

## Semantic links

→ [[tools-enrich-c7]]
→ [[scripts-embed-tracks]]
→ [[pipeline-fetcher-models]]
→ [[models-metadata-cluster]]
→ [[models-genre-predictor]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-meta-spotify-bulk-enrich-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-consensus-py]]
→ [[cursor-ingest/2026-08-04-072347-tools-enrich-c7-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-track-store-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
