# phi / models / meta_clipper.py

#source #python

> path: phi/models/meta_clipper.py  
> ext: .py  

---

# phi / models / meta_clipper.py

phi.models.meta_clipper — per-track metadata embedding for the D4 pipeline.

Pipeline
--------

    text  (title + artist + album + genre — lowercased, concatenated)
      │
      ▼
    TF-IDF(max_features=5 000, ngram_range=(1,2), sublinear_tf=True)
      │   sparse (N, V)
      ▼
    TruncatedSVD(n_components=36) + L2 row-norm
      │   dense (N, 36)   →  clipper_emb  ← fed into D4XGBoostModel
      ▼
    PCA(n_components=2)
      │
    MinMaxScaler → [0.02, 0.98]²
      │   (N, 2)  →  clipper_x, clipper_y  ← track's position on the curve
      ▼
    DragonCurve.fold_bits + score_b  →  fold_

Defines: _meta_to_text, MetaClipper, __init__, _texts, fit, transform, run_batch, save, load, __repr__

---

## Semantic links

→ [[scripts-embed-tracks]]
→ [[tools-enrich-c7]]
→ [[pipeline-sources-youtube-music]]
→ [[pipeline-sources-soundcloud]]
→ [[pipeline-fetcher-models]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-meta-enricher-py]]
→ [[cursor-ingest/2026-08-04-072347-scripts-embed-tracks-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-embed-tracks-md]]
→ [[cursor-ingest/2026-08-04-072347-tools-enrich-c7-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-dataset-export-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
