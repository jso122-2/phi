# phi / models / psp_index.py

#source #python

> path: phi/models/psp_index.py  
> ext: .py  

---

# phi / models / psp_index.py


phi.models.psp_index — Stage I P_sps pre-computation SQLite index.

Pre-computes TF-IDF vectors for all tracks and caches them in a SQLite
database with mtime-based invalidation.  H-space scores are NOT cached
because they depend on the current snap.H which changes when the library
is rescanned.

Schema
------
  tracks  : one row per track — path (PK), text, mtime, tfidf_vec (blob)
  vocab   : single row (id=1) — JSON-serialised list[str] of TF-IDF terms

Consistency contract
--------------------
When any track is dirty the full TF-IDF corpus is rebuilt (to keep IDF
weights correct).  If the 

Defines: PspEntry, _get_mtime, PspIndex, __init__, build, vocabulary, tfidf_matrix, track_paths, close, _fetch_vocab

---

## Semantic links

→ [[psspps-scorer]]
→ [[psspps-pipeline]]
→ [[indexer]]
→ [[psspps-find]]
→ [[models-metadata-cluster]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-psp-index-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-cache-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-library-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-reader-py]]
→ [[cursor-ingest/2026-08-04-072347-psspps-pipeline-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
