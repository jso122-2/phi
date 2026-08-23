# phi / meta / consensus.py

#source #python

> path: phi/meta/consensus.py  
> ext: .py  

---

# phi / meta / consensus.py

phi.meta.consensus — cross-source metadata reconciliation.

Computes consensus fields from multiple enrichment sources once all
individual source passes are complete.

Functions
---------
bpm_consensus(ann, meta)  → dict   bpm_consensus, bpm_confidence, bpm_sources
genre_consensus(ann, meta) → dict  genre_consensus (list[str], up to 5)
meta_score(ann, meta)      → dict  meta_score (float 0–1), meta_fields_present (int)

All functions return a flat dict ready to merge into an annotation store.
They never raise — failures return empty dicts.


Defines: _octave_correct, bpm_consensus, _norm_genre, genre_consensus, meta_score, _add

---

## Semantic links

→ [[models-metadata-cluster]]
→ [[tools-enrich-c7]]
→ [[engine-phi-session]]
→ [[psspps-find]]
→ [[pipeline-worker-multi-source]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-meta-enricher-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-spotify-bulk-enrich-py]]
→ [[cursor-ingest/2026-08-04-072347-source-tools-enrich-c7-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-octopus-organizer-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-dataset-export-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
