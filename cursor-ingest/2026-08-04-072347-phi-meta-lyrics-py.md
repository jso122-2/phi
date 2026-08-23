# phi / meta / lyrics.py

#source #python

> path: phi/meta/lyrics.py  
> ext: .py  

---

# phi / meta / lyrics.py

phi.meta.lyrics — lyrics retrieval.

Two sources tried in order:
  1. Embedded in the audio file  (ID3 USLT, Vorbis LYRICS / UNSYNCEDLYRICS)
  2. lrclib.net public API        (no key, generous rate-limits)

Returns plain text with timestamps stripped.
Safe to call from any thread.


Defines: read_embedded, _strip_timestamps, fetch_lrclib, get_lyrics

---

## Semantic links

→ [[scripts-embed-tracks]]
→ [[pipeline-sources-soundcloud]]
→ [[pipeline-sources-youtube-music]]
→ [[pipeline-sources-internet-archive]]
→ [[tools-enrich-c7]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-library-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-init-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-internet-archive-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-enricher-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-spotify-bulk-enrich-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
