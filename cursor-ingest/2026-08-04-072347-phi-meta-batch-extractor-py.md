# phi / meta / batch_extractor.py

#source #python

> path: phi/meta/batch_extractor.py  
> ext: .py  

---

# phi / meta / batch_extractor.py

phi.meta.batch_extractor — parallel local feature extraction.

Extracts audio features from every track in the phi library using only
local tools (mutagen + librosa).  No API keys required.

Output: ~/.phi/meta_store.jsonl — one JSON object per line, one per track.
Existing records are updated (not duplicated) on re-runs.

Usage
-----
    # CLI — extract all tracks in state.json
    python -m phi.meta.batch_extractor

    # With options
    python -m phi.meta.batch_extractor --workers 6 --force

    # From Python
    from phi.meta.batch_extractor import run_extraction
    run_extraction(paths,

Defines: _extract_one, load_store, save_store, _extract_subprocess, run_extraction, main, _get

---

## Semantic links

→ [[scripts-embed-tracks]]
→ [[pipeline-sources-soundcloud]]
→ [[pipeline-sources-youtube-music]]
→ [[pipeline-fetcher-models]]
→ [[tools-enrich-c7]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-meta-dataset-export-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-extract-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-librosa-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-track-store-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-populate-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
