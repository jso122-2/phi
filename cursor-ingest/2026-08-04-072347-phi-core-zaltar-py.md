# phi / core / zaltar.py

#source #python

> path: phi/core/zaltar.py  
> ext: .py  

---

# phi / core / zaltar.py

phi.core.zaltar — reverse-Zaltar text-to-playlist engine.

User types a mood, concept, or free text.  Zaltar encodes it with CLAP's
text encoder, searches the library's CLAP audio vectors for the closest
matches, blends in D4 personalisation, and returns 5 tracks ordered for
a smooth mix.

API
---
    from phi.core.zaltar import zaltar_query

    results = zaltar_query("feeling melancholic, 3am, rain on a window", library)
    # → [{"path", "title", "artist", "similarity", "d4", "bpm", "mix_pos"}, ...]

Fallback
--------
If CLAP is not loaded / cached locally, text_to_vec() returns None and
za

Defines: text_to_vec, _d4_for, _bpm_for, mix_order, zaltar_query, _d4_fallback, arc_cost

---

## Semantic links

→ [[scripts-embed-tracks]]
→ [[engine-phi-player]]
→ [[psspps-embedder]]
→ [[models-genre-predictor]]
→ [[2026-07-17T01-33-09Z-CLAPProjection and PhiGraph — DAWN bridge layer]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-models-clap-model-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-smart-playlist-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-similarity-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-init-py]]
→ [[cursor-ingest/2026-08-04-072347-scripts-embed-tracks-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
