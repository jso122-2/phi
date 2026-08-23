# phi / engine / zone_clusterer.py

#source #python

> path: phi/engine/zone_clusterer.py  
> ext: .py  

---

# phi / engine / zone_clusterer.py

phi.engine.zone_clusterer — background k-means clustering on anchored tracks.

Partitions the anchored track library into 8 zones using k-means on the
4-dimensional feature space:

    [clipper_x, clipper_y, d4_a / 20.0, d4_b / 20.0]

The first two dimensions are the BPM × Key projection in [0,1]²; the last two
normalise the dragon-curve D4 scores (range ≈ [0, 20]) into the same scale.

Zones are indexed 0–7 to match the 8 harmonic shards in the CAIRRN ring.
Zone assignment is written back to the ``annotations`` table of MetaCache and
emitted via the ``clustered`` signal for in-memory caching 

Defines: ZoneClusterer, __init__, start_if_ready, run, _run_inner, _build_transition_matrix

---

## Semantic links

→ [[scripts-train-d4]]
→ [[models-metadata-cluster]]
→ [[engine-phi-session]]
→ [[engine-tracer-daemon]]
→ [[engine-vault-garden]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-dragon-room-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-curve-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-ui-qt-rooms-dragon-coord-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-curve-walker-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-dragon-curve-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
