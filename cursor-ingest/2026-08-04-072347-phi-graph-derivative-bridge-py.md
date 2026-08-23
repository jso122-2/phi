# phi / graph / derivative_bridge.py

#source #python

> path: phi/graph/derivative_bridge.py  
> ext: .py  

---

# phi / graph / derivative_bridge.py


phi.graph.derivative_bridge — bind SongDerivativeModel D4 scores to the PhiGraph.

This module is the seam between the two ML systems:

    SongDerivativeModel (XGBoost, acoustic + social features)
            ↓  {path → {d1, d2, d3, d4}}
    derivative_bridge
            ↓  d4_scores: np.ndarray (N,)  aligned to PhiGraphSnapshot.paths
    PhiGraphSnapshot.d4_scores
            ↓
    cluster_d4_profile()  — per-cluster D4 statistics
    top_k_by_d4()         — rank tracks within a cluster by D4

D4 is the master derivative: the rolling mean of the inbetween mean (D3) across
the sorted library

Defines: score_and_attach, _compute_scores, cluster_d4_profile, top_k_by_d4, _empty_d4_fields

---

## Semantic links

→ [[engine-bridge-factory]]
→ [[engine-arm-injector]]
→ [[2026-07-17T01-33-09Z-CLAPProjection and PhiGraph — DAWN bridge layer]]
→ [[graph-hub-classifier]]
→ [[engine-phi-session]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-models-song-derivative-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-inference-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-metadata-schema-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-orchestrator-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-builder-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
