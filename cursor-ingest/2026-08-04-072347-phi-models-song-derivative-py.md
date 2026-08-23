# phi / models / song_derivative.py

#source #python

> path: phi/models/song_derivative.py  
> ext: .py  

---

# phi / models / song_derivative.py

phi.models.song_derivative — hierarchical XGBoost derivative scorer.

Computes four derivative scores (D_1 → D_4) for every song in the library.
All input features are percentile-rank quantized to [0, 1] so that features
measured in different units (Hz, BPM, listener counts) compete on equal footing.

Architecture
------------

            D_4  (master — rolling mean of D_3 across sorted library)
          /      \
       D_1         D_2      (two XGBoost arms)
          \      /
            D_3  (inbetween mean of D_1 and D_2)

Dragon-curve fold:
  D_1 = XGBoost on acoustic + tonal features  

Defines: _rolling_mean, SongDerivativeModel, score_library, _main, __init__, score_library, _norm, _drop_dead_cols

---

## Semantic links

→ [[models-genre-predictor]]
→ [[models-metadata-cluster]]
→ [[engine-phi-player]]
→ [[scripts-train-d4]]
→ [[scripts-embed-tracks]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-graph-derivative-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-inference-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-derivative-features-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-derivative-loaders-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-d4-model-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
