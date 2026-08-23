# phi / core / similarity.py

#source #python

> path: phi/core/similarity.py  
> ext: .py  

---

# phi / core / similarity.py

phi.core.similarity — nearest-neighbour search over CLAP audio vectors.

Once CLAPModel has run over the library, every track has a 'mood_vec'
stored in Library.annotations.  This module does fast cosine similarity
search over those vectors to implement:

    find_similar(path, library, n=10)  →  list of (path, score) pairs

When a ForestFloor is bound (via ``bind_floor``), similarity search is
routed through a CAIRRN MATH-gated PhiSimilarityIndex — a precomputed
(n × d) numpy matrix.  One matrix-vector multiply replaces the O(n × d)
Python loop, giving ~200× speedup on a 1000-track library.



Defines: set_scheduler, bind_floor, _invalidate_similarity, _get_similarity_index, _cosine_py, _cosine, find_similar, find_similar_to_vec, coverage, build_radio, _bpm_radio, _on_math_shift

---

## Semantic links

→ [[scripts-embed-tracks]]
→ [[psspps-scorer]]
→ [[psspps-traverser]]
→ [[models-genre-predictor]]
→ [[models-metadata-cluster]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-engine-similarity-index-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-clap-model-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-builder-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-zaltar-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
