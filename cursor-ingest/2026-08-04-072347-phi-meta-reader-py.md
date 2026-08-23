# phi / meta / reader.py

#source #python

> path: phi/meta/reader.py  
> ext: .py  

---

# phi / meta / reader.py

phi.meta.reader — tag reading for any audio format via mutagen.

Primary entry points
--------------------
read_meta(path)                 — full mutagen scan, always reads from disk
read_meta_cached(path, cache)   — checks SQLite cache first, falls back to mutagen
scan_folder_cached(folder, cache) — bulk scan with cache awareness


Defines: read_meta_cached, bulk_prime_cache, read_meta, track_sort_key, scan_folder, scan_folder_cached, first

---

## Semantic links

→ [[scripts-embed-tracks]]
→ [[scripts-bake-ascii]]
→ [[engine-phi-player]]
→ [[engine-phi-session]]
→ [[README]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-meta-cache-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-discovery-py]]
→ [[cursor-ingest/2026-08-04-072347-scripts-embed-tracks-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-lastfm-meta-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
