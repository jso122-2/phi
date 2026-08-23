# scripts / embed_tracks.py

#source #python

> path: scripts/embed_tracks.py  
> ext: .py  

---

# scripts / embed_tracks.py

embed_tracks.py — pre-compute 512-d MetadataEncoder embeddings for phi tracks.

Scans the library for audio files that do not yet have a <track>.npy sidecar
and generates embeddings using the pure-numpy MetadataEncoder (no GPU, no CLAP
model required).  Once saved, phi._loader picks them up automatically on next
library scan and CLAPProjection uses them as Tier-1 input.

Usage
-----
    python scripts/embed_tracks.py                    # watch + fill continuously
    python scripts/embed_tracks.py --once             # one pass then exit
    python scripts/embed_tracks.py --root /path       # o

Defines: _library_root, _scan_missing, _embed_one, run_pass, main

---

## Semantic links

→ [[scripts-embed-tracks]]
→ [[pipeline-sources-soundcloud]]
→ [[engine-phi-player]]
→ [[engine-phi-session]]
→ [[tools-enrich-c7]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-scripts-embed-tracks-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-clap-model-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-clap-proj-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-audio-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-loader-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
