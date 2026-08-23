# phi / meta / dataset_export.py

#source #python

> path: phi/meta/dataset_export.py  
> ext: .py  

---

# phi / meta / dataset_export.py

phi.meta.dataset_export — turn meta_store into ML-ready training data.

Reads ~/.phi/meta_store.jsonl (built by batch_extractor) and exports:

  ~/.phi/dataset/
    dataset.jsonl       — one enriched record per track (all fields)
    features.npy        — float32 matrix  (N × D)
    feature_names.json  — column names for features.npy
    labels.json         — discrete bucket assignments per track
    splits.json         — train / val / test path lists (80/10/10, artist-stratified)
    stats.json          — dataset statistics and bucket distributions

Bucket definitions
------------------
mood 

Defines: _load_annotations, _mood_bucket, _energy_level, _tempo_class, _key_mode, _genre_label, _feature_vector, _split, export, main, _f, _pad, _pct

---

## Semantic links

→ [[pipeline-fetcher-models]]
→ [[models-metadata-cluster]]
→ [[scripts-embed-tracks]]
→ [[tools-enrich-c7]]
→ [[2025-08-13-102831-2025-08-13t20-40-07-038-10-00]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-meta-batch-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-track-store-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-derivative-loaders-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-loader-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-meta-clipper-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
