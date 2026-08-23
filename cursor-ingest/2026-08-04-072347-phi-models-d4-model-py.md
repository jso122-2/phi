# phi / models / d4_model.py

#source #python

> path: phi/models/d4_model.py  
> ext: .py  

---

# phi / models / d4_model.py

phi.models.d4_model — D4 XGBoost regression model (baseline).

Baseline ML model from scribble-002 / dragon curve design:

Feature vector  (45 dimensions):
    [0:36]   clipper_emb   — 36-d reduction from GeminiClipper (6×6 matrix, col-major)
    [36:44]  fold_bits     — 8-bit dragon curve positional encoding
    [44]     d4_b          — D4_B fold-direction score

Target:
    d4_a  — D4_A norm-ratio score  (rolling mean of ‖D3‖/‖D1‖ − D2)

Training:
    GeminiClipper.run_batch()  →  annotation dicts + rolling_d4a target array
    D4XGBoostModel.fit(annotations, rolling_d4a)

Inference:
    Phi

Defines: _build_feature_row, _build_feature_matrix, D4XGBoostModel, __init__, _make_regressor, fit, can_process, run, predict_batch, feature_importance, save, load

---

## Semantic links

→ [[scripts-train-d4]]
→ [[models-bert-clipper]]
→ [[models-arms]]
→ [[models-suckers]]
→ [[models-genre-predictor]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-scripts-train-d4-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-dragon-curve-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-dragon-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-zone-clusterer-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-song-derivative-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
