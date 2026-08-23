# phi / meta / mb_client.py

#source #python

> path: phi/meta/mb_client.py  
> ext: .py  

---

# phi / meta / mb_client.py

phi.meta.mb_client — MusicBrainz + CoverArtArchive fetch layer.

Rate-limited to ≤ 10 requests / second (MusicBrainz policy requires a
proper User-Agent and allows 1 req/sec anonymous; 10 req/sec with a
registered User-Agent string).

All methods return None / {} on failure rather than raising so the
enrichment pipeline can degrade gracefully.


Defines: MBRecording, _RateLimiter, MusicBrainzClient, as_meta_dict, as_annotation_dict, __init__, wait, __init__, fetch_recording, fetch_artist, fetch_cover_art

---

## Semantic links

→ [[fetcher]]
→ [[2026-07-15]]
→ [[pipeline-sources-youtube-music]]
→ [[pipeline-fetcher-models]]
→ [[index]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-watch-enrich-daemon-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-discogs-client-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-spotify-client-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-lastfm-meta-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-fetcher-models-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
