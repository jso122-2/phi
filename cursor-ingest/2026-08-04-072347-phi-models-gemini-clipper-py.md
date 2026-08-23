# phi / models / gemini_clipper.py

#source #python

> path: phi/models/gemini_clipper.py  
> ext: .py  

---

# phi / models / gemini_clipper.py


GeminiClipper — Stage III execution engine for the phi model.

Architecture (keep/2025-12-06-114407-gemini-clipper):

    query
      │
      ├─► Semantic scoring  (TF-IDF over track text)          sem ∈ [0,1]^N
      │
      └─► H-space proximity (query encoded → cosine on H)     h_space ∈ [0,1]^N
              │
              ▼
          P_sps = (1−α)·sem + α·h_space
              │
              ▼
          top-K ClippedTrack  ranked by P_sps
              │
              ▼
          ClipResult.context  — compact metadata blocks ready for LLM synthesis

Query → H-space path:
    Parse quer

Defines: _track_text, _query_h_vec, _format_duration, _format_context_block, ClippedTrack, ClipResult, GeminiClipper, __init__, clip, __repr__

---

## Semantic links

→ [[mcp-server-tools-phi-clip]]
→ [[models-bert-clipper]]
→ [[2025-12-06-114407-gemini-clipper]]
→ [[engine-phi-session]]
→ [[psspps-scorer]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-models-query-router-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-gemini-clipper-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-phi-clip-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-session-clip-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-phi-clip-tool-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
