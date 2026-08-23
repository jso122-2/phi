# models / genre_predictor.py

#source #python

> path: models/genre_predictor.py  
> ext: .py  

---

# models / genre_predictor.py


models.genre_predictor — XGBoost-backed genre predictor for PhiLibrary.

Uses the trained xgb_cluster.json model (k=8 clusters) to assign a genre
label to any Track.  Cluster → genre label is derived from the dominant tag
activation per cluster using the saved X_encoded.npy + labels.npy artifacts.

Lookup order for genre_for(track):
    1. cluster_map.json  (O(1) dict — known tracks from training run)
    2. XGBoost predict   (encode_one → clf.predict for unseen tracks)
    3. cluster_genre()   → human-readable tag-derived label


Defines: GenrePredictor, __init__, _derive_cluster_labels, predict_cluster, cluster_id_for, cluster_genre, genre_for, genre_summary, __repr__

---

## Semantic links

→ [[models-genre-predictor]]
→ [[models-metadata-cluster]]
→ [[tools-enrich-c7]]
→ [[scripts-embed-tracks]]
→ [[GENRE]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-models-metadata-cluster-py]]
→ [[cursor-ingest/2026-08-04-072347-source-models-genre-predictor-md]]
→ [[cursor-ingest/2026-08-04-072347-tools-enrich-c7-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-track-store-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-genre-renderer-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
