# phi / models / clap_proj.py

#source #python

> path: phi/models/clap_proj.py  
> ext: .py  

---

# phi / models / clap_proj.py


CLAPProjection — bridges audio embeddings into OctopusTracer's H space.

Architecture (LOCKED — CLAPProjection and PhiGraph agent-log):

    CLAPProjection: single Linear(512, 256) + L2-normalised output.
    CLAP's 512-d audio vectors are geometrically aligned (contrastive
    language-audio training) — a linear rotation/scale is sufficient.

Two embedding sources (pre-computed .npy path wins; metadata fallback):

    1. Pre-computed CLAP  — load <track>.npy (512-d float32 vector)
                            → CLAPProjection(512→256) → L2-norm
    2. MetadataEncoder    — encode JSON metadata

Defines: CLAPProjection, embed_tracks, __init__, forward, d_model, d_clap, n_params, project_library, __repr__

---

## Semantic links

→ [[2026-07-17T01-33-09Z-CLAPProjection and PhiGraph — DAWN bridge layer]]
→ [[scripts-embed-tracks]]
→ [[models-init]]
→ [[models-octopus-head]]
→ [[models-suckers]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-meta-meta-embedder-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-clap-model-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-gnn-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
