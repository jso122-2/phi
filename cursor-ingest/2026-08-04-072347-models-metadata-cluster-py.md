# models / metadata_cluster.py

#source #python

> path: models/metadata_cluster.py  
> ext: .py  

---

# models / metadata_cluster.py


models.metadata_cluster — unsupervised clustering of Spotify metadata.

Pipeline
--------
1.  PhiLibrary.scan()       → 372 Track objects
2.  MetadataEncoder.encode() → (N, 512) float64
3.  L2-normalise + PCA       → (N, n_components) via numpy SVD
4.  K-means                  → cluster labels  (scipy.cluster.vq)
5.  XGBoost classifier       → trained on cluster labels → feature importance
6.  Save artefacts to  models/cluster_out/

Usage
-----
    python -m models.metadata_cluster          # default k=8
    python -m models.metadata_cluster --k 12
    python -m models.metadata_cluster --k 8 

Defines: _feature_names, pca_fit, pca_transform, run, _save_importance_plot

---

## Semantic links

→ [[models-metadata-cluster]]
→ [[models-genre-predictor]]
→ [[tools-enrich-c7]]
→ [[index]]
→ [[pipeline-fetcher-models]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-models-metadata-cluster-md]]
→ [[cursor-ingest/2026-08-04-072347-models-genre-predictor-py]]
→ [[cursor-ingest/2026-08-04-072347-tools-enrich-c7-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-octopus-organizer-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-spotify-bulk-enrich-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
