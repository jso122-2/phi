# source / psspps-pipeline.md

#doc #md

> path: source/psspps-pipeline.md  
> ext: .md  

---

# psspps/pipeline

#code #module #psspps #code

> source_path: psspps/pipeline.py  
> package: psspps  
> module: psspps/pipeline  
> hub: CODE  
> created_ts:   

---

**Package:** `psspps`  
**Module:** `psspps/pipeline`  
**Source:** `psspps/pipeline.py`

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

## API

- `class ScoredDoc`
- `class PSPSPSResult`
- `def run_psspps` — Execute the full PSSPPS pipeline.
- `def _empty`

## Internal imports

`psspps.retriever`, `psspps.router`, `psspps.scorer`

---

## Semantic links

→ [[psspps]]
→ [[psspps]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[CODE]]
→ [[CODE]]

## Related notes

→ [[source/psspps-init]]
→ [[source/psspps-router]]
→ [[source/psspps-retriever]]
→ [[source/psspps-find]]
→ [[source/mcp-server-tools-search]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[psspps-init]]
→ [[psspps-retriever]]
→ [[psspps-index]]
→ [[psspps-router]]
→ [[mcp-server-tools-search]]
→ [[psspps-scorer]]

---

## Semantic links

→ [[psspps-pipeline]]
→ [[psspps-router]]
→ [[psspps-retriever]]
→ [[pipeline-utils-config]]
→ [[pipeline-fetcher-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-psspps-pipeline-py]]
→ [[cursor-ingest/2026-08-04-072347-source-psspps-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-psspps-router-md]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-search-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-utils-config-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
