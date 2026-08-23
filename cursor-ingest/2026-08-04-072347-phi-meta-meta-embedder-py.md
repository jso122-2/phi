# phi / meta / _meta_embedder.py

#source #python

> path: phi/meta/_meta_embedder.py  
> ext: .py  

---

# phi / meta / _meta_embedder.py

phi.meta._meta_embedder — three-tier track embedding for OctopusOrganizer.

Builds the (N, d_model) matrix H that OctopusTracer ingests:

  Tier 1  CLAP audio vector (512-d) → CLAPProjection → 256-d  (rich)
  Tier 2  librosa features (19-d)   → fixed random projection   (sparse)
  Tier 3  stable random vector      → seeded by path hash        (cold)

Tiers 2/3 are informationally thin; the tracer's sprout arm correctly flags
these tracks as graph-isolated, pushing them to the front of the enrich queue.


Defines: MetaEmbedder, __init__, load_librosa_store, embed, _embed_librosa, _embed_random

---

## Semantic links

→ [[models-init]]
→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]
→ [[models-octopus-head]]
→ [[scripts-embed-tracks]]
→ [[models-metadata-cluster]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-models-clap-proj-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-octopus-organizer-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-gnn-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-metadata-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
