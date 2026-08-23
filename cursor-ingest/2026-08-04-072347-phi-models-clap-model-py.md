# phi / models / clap_model.py

#source #python

> path: phi/models/clap_model.py  
> ext: .py  

---

# phi / models / clap_model.py

phi.models.clap_model — CLAP-based mood + genre vector extraction.

Lazy ML upgrade for MoodModel and genre affinity.

When ``torch`` and ``transformers`` are importable and
``laion/clap-htsat-fused`` is available, this model runs each audio file
through CLAP to produce:

    mood_vec   : list[float]  — 512-d audio embedding (mood-sensitive)
    genre_vec  : list[float]  — same embedding reused; ranker uses it for
                               cosine genre affinity
    mood_source: "clap"       — signals MoodModel to skip re-classification

When dependencies are absent, ``can_process()`` retu

Defines: needs_reprocess, clear_reprocess, bind_floor, CLAPModel, _cosine, _on_math_shift, _load, _precompute_text_vecs, can_process, run, _encode_audio

---

## Semantic links

→ [[scripts-embed-tracks]]
→ [[2026-07-17T01-33-09Z-CLAPProjection and PhiGraph — DAWN bridge layer]]
→ [[models-genre-predictor]]
→ [[models-metadata-cluster]]
→ [[MOOD]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-scripts-embed-tracks-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-clap-proj-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-similarity-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-zaltar-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-builder-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
