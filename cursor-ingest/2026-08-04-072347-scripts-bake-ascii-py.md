# scripts / bake_ascii.py

#source #python

> path: scripts/bake_ascii.py  
> ext: .py  

---

# scripts / bake_ascii.py


scripts/bake_ascii.py — one-shot batch bake for coloured ASCII album art.

Reads every track row in ~/.phi/meta.db that has art_bytes, converts each
unique image to a coloured ASCII grid, and writes it to:

    ~/.phi/ascii/<sha1[:2]>/<sha1[2:]>_64x32.json

Idempotent — already-baked files are skipped, not re-converted.
Requires only PIL (no Tk, no pygame, no objc).

Usage
-----
    cd /path/to/Spotify-rip
    mamba activate spotify-rip
    python scripts/bake_ascii.py

    # or point at a different DB:
    python scripts/bake_ascii.py --db /path/to/meta.db


Defines: _bake_path, _bake, run, main

---

## Semantic links

→ [[scripts-bake-ascii]]
→ [[scripts-embed-tracks]]
→ [[index]]
→ [[obsidian-exporter]]
→ [[models-metadata-cluster]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-meta-art-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-bake-ascii-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-batch-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-dataset-export-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-reader-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
