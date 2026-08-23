# psspps / pipeline.py

#source #python

> path: psspps/pipeline.py  
> ext: .py  

---

# psspps / pipeline.py


Full PSSPPS pipeline.

  query
    │
    ▼
  Router (pre)          → skip retrieval for slash-commands / trivial queries
    │
    ▼
  Retriever             → load all Obsidian vault .md files
    │
    ▼
  Scorer (semantic)     → TF-IDF cosine similarity
  Scorer (perspective)  → harmonic index activation × basin affinity
  Combined score        → (1−α)·semantic + α·perspective
    │
    ▼
  Router (post)         → was RAG actually useful? (lift over mean)
    │
    ▼
  PSPSPSResult          → ranked docs + all scores + routing signals


Defines: ScoredDoc, PSPSPSResult, run_psspps, _empty

---

## Semantic links

→ [[psspps-pipeline]]
→ [[psspps-init]]
→ [[psspps-router]]
→ [[psspps-retriever]]
→ [[VAULT]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-psspps-init-py]]
→ [[cursor-ingest/2026-08-04-072347-psspps-md]]
→ [[cursor-ingest/2026-08-04-072347-psspps-router-py]]
→ [[cursor-ingest/2026-08-04-072347-source-psspps-pipeline-md]]
→ [[cursor-ingest/2026-08-04-072347-source-psspps-find-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
