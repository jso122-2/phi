# phi / engine / similarity_index.py

#source #python

> path: phi/engine/similarity_index.py  
> ext: .py  

---

# phi / engine / similarity_index.py

phi.engine.similarity_index — numpy-accelerated cosine similarity search.

``PhiSimilarityIndex`` builds a precomputed (N × D) float32 matrix over CLAP
vectors and executes O(1) nearest-neighbour queries via a single matrix-vector
multiply.  Falls back gracefully when numpy is unavailable.

Invalidated by the MATH hub: when MATH loses coherence (after ~20 CLAP
annotation batches) the index is rebuilt automatically via the
``bind_floor`` subscription in phi.core.similarity.


Defines: PhiSimilarityIndex, __init__, build, find_similar, find_similar_to_vec, size, age_secs

---

## Semantic links

→ [[models-metadata-cluster]]
→ [[harmonic-index]]
→ [[harmonic-index]]
→ [[engine-coherence-daemon]]
→ [[MATH]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-core-similarity-py]]
→ [[cursor-ingest/2026-08-04-072347-psspps-scorer-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-coherence-gate-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-constants-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-psp-index-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
