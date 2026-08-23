# phi / metadata / node_builder.py

#source #python

> path: phi/metadata/node_builder.py  
> ext: .py  

---

# phi / metadata / node_builder.py

phi.metadata.node_builder — assemble a 6-node SongNode window.

Public API
----------
    nodes = build_window(tracks)
        list[Track] (≤6) → list[SongNode]
        Runs librosa extraction on each track's audio path.
        Assigns node_id (0–5) and CAIRRN shard from _SHARD_MAP.
        degree is 0 at build time — populated by the adjacency layer.

    nodes = build_window(tracks, extract_audio=False)
        Skip librosa extraction; AudioFeatures zeroed.
        Useful for testing or when audio files are not yet available.


Defines: build_window, update_degrees

---

## Semantic links

→ [[engine-vault-garden]]
→ [[tools-enrich-c7]]
→ [[graph-node]]
→ [[models-metadata-cluster]]
→ [[pipeline-sources-soundcloud]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-metadata-schema-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-metadata-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-metadata-extractor-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
