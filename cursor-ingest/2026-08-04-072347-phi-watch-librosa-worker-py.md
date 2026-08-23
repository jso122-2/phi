# phi / watch / librosa_worker.py

#source #python

> path: phi/watch/librosa_worker.py  
> ext: .py  

---

# phi / watch / librosa_worker.py

phi.watch.librosa_worker — background librosa feature extraction.

Processes library tracks one at a time, extracting local audio features
(BPM, key, spectral, MFCC) using librosa via a sandboxed subprocess with
a hard 25s timeout per track.

Each successful extraction:
  - Writes a full feature record to ~/.phi/meta_store.jsonl
  - Pushes librosa_bpm / librosa_key / librosa_key_idx / librosa_enriched
    into Library annotations so bpm_consensus sees the signal immediately

No API keys required. CPU-bound (~1–3s per track for 60s audio).
Pauses automatically while audio is playing.

Usage (in

Defines: LibrosaProgress, LibrosaWorker, pct, status_line, __init__, start, stop, progress, _run, _pending_paths, _process, _apply_result, _notify

---

## Semantic links

→ [[pipeline-fetcher-models]]
→ [[scripts-embed-tracks]]
→ [[index]]
→ [[engine-phi-session]]
→ [[pipeline-sources-soundcloud]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-meta-batch-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-metadata-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-enrich-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-extract-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-spectrogram-worker-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
