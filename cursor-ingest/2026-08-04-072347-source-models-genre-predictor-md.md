# source / models-genre-predictor.md

#doc #md

> path: source/models-genre-predictor.md  
> ext: .md  

---

# models/genre_predictor

#code #module #models #math

> source_path: models/genre_predictor.py  
> package: models  
> module: models/genre_predictor  
> hub: MATH  
> created_ts:   

---

**Package:** `models`  
**Module:** `models/genre_predictor`  
**Source:** `models/genre_predictor.py`

models.genre_predictor — XGBoost-backed genre predictor for PhiLibrary.

Uses the trained xgb_cluster.json model (k=8 clusters) to assign a genre
label to any Track.  Cluster → genre label is derived from the dominant tag
activation per cluster using the saved X_encoded.npy + labels.npy artifacts.

Lookup order for genre_for(track):
    1. cluster_map.json  (O(1) dict — known tracks from training run)
    2. XGBoost predict   (encode_one → clf.predict for unseen tracks)
    3. cluster_genre()   → human-readable tag-derived label

## API

- `class GenrePredictor` — Predict the genre cluster for any Track using the trained XGBoost model.

---

## Semantic links

→ [[2026-07-16-011935-mamba-environment-spotify-rip]]
→ [[index]]
→ [[scheduler]]
→ [[indexer]]
→ [[2024-08-27-133515-celeste-scribble]]

## Related notes

→ [[source/models-metadata-cluster]]
→ [[source/tools-enrich-c7]]
→ [[source/scripts-embed-tracks]]
→ [[source/pipeline-fetcher-models]]
→ [[source/models-init]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[models-metadata-cluster]]
→ [[models-index]]
→ [[models-init]]
→ [[scripts-embed-tracks]]
→ [[pipeline-fetcher-init]]
→ [[models-octopus-head]]

---

## Semantic links

→ [[models-genre-predictor]]
→ [[models-init]]
→ [[models-metadata-cluster]]
→ [[pipeline-fetcher-models]]
→ [[scripts-embed-tracks]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-models-genre-predictor-py]]
→ [[cursor-ingest/2026-08-04-072347-source-models-index-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-genre-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-models-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-genre-renderer-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
