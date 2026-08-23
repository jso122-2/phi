# phi / meta / _spectrogram_worker.py

#source #python

> path: phi/meta/_spectrogram_worker.py  
> ext: .py  

---

# phi / meta / _spectrogram_worker.py

phi.meta._spectrogram_worker — subprocess spectrogram extractor.

Called by track_store.py as:
    python _spectrogram_worker.py <audio_path> <output_dir>

Writes three .npy files into <output_dir>/:
    mel_128.npy     float32 (T, 128)  log-mel spectrogram
    chroma_12.npy   float32 (T, 12)   chromagram (CQT-based)
    tonnetz_6.npy   float32 (T, 6)    tonal centroid features

Exits with code 0 on success, non-zero on failure.
Stderr is suppressed by the caller.


Defines: main

---

## Semantic links

→ [[scripts-embed-tracks]]
→ [[engine-phi-session]]
→ [[pipeline-sources-soundcloud]]
→ [[pipeline-fetcher-models]]
→ [[models-metadata-cluster]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-meta-extract-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-librosa-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-enrich-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-batch-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-metadata-extractor-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
