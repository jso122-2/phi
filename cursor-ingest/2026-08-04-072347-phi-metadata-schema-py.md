# phi / metadata / schema.py

#source #python

> path: phi/metadata/schema.py  
> ext: .py  

---

# phi / metadata / schema.py

phi.metadata.schema — Three-layer song node schema.

Layer 1  Editorial  — sourced from phi._track.Track (ID3 + enrichment JSON)
Layer 2  Audio      — AudioFeatures, librosa-computed from local audio file
Layer 3  Graph      — GraphPosition, assigned at window build time

SongNode binds all three layers for a single track in a 6-node window.


Defines: AudioFeatures, GraphPosition, SongNode, to_vector, __post_init__, __post_init__, node_id, shard, display, __repr__

---

## Semantic links

→ [[scripts-embed-tracks]]
→ [[graph-node]]
→ [[pipeline-sources-soundcloud]]
→ [[tools-enrich-c7]]
→ [[pipeline-sources-youtube-music]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-metadata-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-metadata-node-builder-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-builder-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-track-store-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
