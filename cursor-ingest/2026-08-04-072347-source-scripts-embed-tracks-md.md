# source / scripts-embed-tracks.md

#doc #md

> path: source/scripts-embed-tracks.md  
> ext: .md  

---

# scripts/embed_tracks

#code #module #scripts #code

> source_path: scripts/embed_tracks.py  
> package: scripts  
> module: scripts/embed_tracks  
> hub: CODE  
> created_ts:   

---

**Package:** `scripts`  
**Module:** `scripts/embed_tracks`  
**Source:** `scripts/embed_tracks.py`

embed_tracks.py — pre-compute 512-d MetadataEncoder embeddings for phi tracks.

Scans the library for audio files that do not yet have a <track>.npy sidecar
and generates embeddings using the pure-numpy MetadataEncoder (no GPU, no CLAP
model required).  Once saved, phi._loader picks them up automatically on next
library scan and CLAPProjection uses them as Tier-1 input.

Usage
-----
    python scripts/embed_tracks.py                    # watch + fill continuously
    python scripts/embed_tracks.py --once             # one pass then exit
    python scripts/embed_tracks.py --root /path       # override library root
    python scripts/embed_tracks.py --dry-run          # print paths, no writes
    python scripts/embed_tracks.py --workers 4        # parallel workers (default 2)

Output
------
    <track_audio_path>.npy  (float32, shape (512,))
    Written alongside the audio file so phi._loader.clap_npy resolves it.

## API

- `def _library_root`
- `def _scan_missing` — Return audio paths that have no .npy sidecar.
- `def _embed_one` — Encode one track and write its .npy sidecar.  Returns a status string.
- `def run_pass` — Embed all missing tracks in root.  Returns number processed.
- `def main`

---

## Semantic links

→ [[indexer]]
→ [[index]]
→ [[2026-07-17T01-33-09Z-CLAPProjection and PhiGraph — DAWN bridge layer]]
→ [[obsidian-exporter]]
→ [[fetcher]]

## Related notes

→ [[source/pipeline-sources-soundcloud]]
→ [[source/scripts-rescrape-short]]
→ [[source/tools-enrich-c7]]
→ [[source/models-metadata-cluster]]
→ [[source/models-genre-predictor]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[scripts-rescrape-short]

---

## Semantic links

→ [[scripts-embed-tracks]]
→ [[tools-enrich-c7]]
→ [[models-metadata-cluster]]
→ [[pipeline-fetcher-models]]
→ [[scripts-rescrape-short]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-scripts-embed-tracks-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-rescrape-short-md]]
→ [[cursor-ingest/2026-08-04-072347-tools-enrich-c7-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-index-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-meta-clipper-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
