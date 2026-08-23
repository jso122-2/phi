# phi / meta / octopus_organizer.py

#source #python

> path: phi/meta/octopus_organizer.py  
> ext: .py  

---

# phi / meta / octopus_organizer.py

phi.meta.octopus_organizer — OctopusTracer-driven metadata organisation pipeline.

Run OctopusTracer *before* enrichment to decide:
  - Which tracks to enrich first (sprout + resurface signal)
  - Which tracks are probably corrupt / skip enrichment (prune signal)
  - Which near-duplicate pairs to surface for user review (merge arm)
  - What cluster a track belongs to (cluster arm)
  - What tags the model thinks a track should carry (tag arm)

Priority formula::

    enrich_priority = sprout × (1 − prune) + resurface × 0.30

Usage::

    from phi.meta.octopus_organizer import OctopusOrganizer, 

Defines: OctopusOrganizer, make_organizer, __init__, organise

---

## Semantic links

→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]
→ [[models-init]]
→ [[tools-enrich-c7]]
→ [[models-metadata-cluster]]
→ [[pipeline-worker-fs-organizer]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-meta-octopus-types-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-meta-embedder-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-tracer-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-octopus-arms-py]]
→ [[cursor-ingest/2026-08-04-072347-tools-enrich-c7-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
