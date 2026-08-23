# source / scripts-bake-ascii.md

#doc #md

> path: source/scripts-bake-ascii.md  
> ext: .md  

---

# scripts/bake_ascii

#code #module #scripts #code

> source_path: scripts/bake_ascii.py  
> package: scripts  
> module: scripts/bake_ascii  
> hub: CODE  
> created_ts:   

---

**Package:** `scripts`  
**Module:** `scripts/bake_ascii`  
**Source:** `scripts/bake_ascii.py`

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

## API

- `def _bake_path`
- `def _bake` — Convert art_bytes → JSON grid.  Returns True on success.
- `def run`
- `def main`

---

## Semantic links

→ [[index]]
→ [[2026-03-15-101605-2026-03-15t21-16-05-875-11-00]]
→ [[obsidian-exporter]]
→ [[mcp-server]]
→ [[2026-07-16T19-50-20Z-phi floating UI + ASCII waveform — Layer 5 implementation]]

## Related notes

→ [[source/scripts-embed-tracks]]
→ [[source/models-metadata-cluster]]
→ [[source/engine-phi-session]]
→ [[source/tools-enrich-c7]]
→ [[source/scripts-rescrape-short]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[scripts-index]]
→ [[scripts-embed-tracks]]
→ [[scripts-rescrape-short]]
→ [[scripts-train-d4]]
→ [[scripts-train]]
→ [[scripts-mcp-bridge]]

---

## Semantic links

→ [[scripts-bake-ascii]]
→ [[scripts-train]]
→ [[scripts-pretrain-loop]]
→ [[engine-main]]
→ [[mcp-server-tools-modular]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-main-md]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-samba-mcp-server-md]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-init-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-bake-ascii-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
