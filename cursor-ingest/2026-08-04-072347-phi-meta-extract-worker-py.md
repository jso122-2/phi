# phi / meta / _extract_worker.py

#source #python

> path: phi/meta/_extract_worker.py  
> ext: .py  

---

# phi / meta / _extract_worker.py

Single-track extraction worker — spawned by batch_extractor via subprocess.

Usage: python _extract_worker.py <audio_path> <output_json_path>

Writes JSON result to output_json_path (temp file) instead of stdout so that
pipe inheritance by ffmpeg/audioread subprocesses never blocks the parent.
Avoids importing phi.meta.__init__ to prevent tkinter/pygame initialisation.


Defines: _load_extractor

---

## Semantic links

→ [[scripts-embed-tracks]]
→ [[pipeline-sources-soundcloud]]
→ [[pipeline-worker-executor]]
→ [[pipeline-worker-fs-organizer]]
→ [[workers-base]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-meta-batch-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-spectrogram-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-librosa-worker-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-enrich-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-metadata-extractor-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
