# source / models-metadata-cluster.md

#doc #md

> path: source/models-metadata-cluster.md  
> ext: .md  

---

# models/metadata_cluster

#code #module #models #math

> source_path: models/metadata_cluster.py  
> package: models  
> module: models/metadata_cluster  
> hub: MATH  
> created_ts:   

---

**Package:** `models`  
**Module:** `models/metadata_cluster`  
**Source:** `models/metadata_cluster.py`

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
    python -m models.metadata_cluster --k 8 --pca 32

## API

- `def _feature_names`
- `def pca_fit` — Centre + SVD PCA.
- `def pca_transform`
- `def run`
- `def _save_importance_plot`

---

## Semantic links

→ [[indexer]]
→ [[fetcher]]
→ [[index]]
→ [[2026-07-16-011935-mamba-environment-spotify-rip]]
→ [[mcp-server]]

## Related notes

→ [[source/tools-enrich-c7]]
→ [[source/models-genre-predictor]]
→ [[source/pipeline-fetcher-models]]
→ [[source/scripts-embed-tracks]]
→ [[source/pipeline-fetcher-init]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[models-index]]
→ [[models-init]]
→ [[models-genre-predictor]]
→ [[pipeline-fetcher-init]]
→ [[pipeline-fetcher-models]]
→ [[models-octopus-head]]

---

## Semantic links

→ [[models-metadata-cluster]]
→ [[pipeline-fetcher-models]]
→ [[tools-enrich-c7]]
→ [[index]]
→ [[fetcher]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-models-metadata-cluster-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-fetcher-models-md]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-fetcher-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-fetcher-init-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-config-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
