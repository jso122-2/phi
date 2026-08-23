# phi / meta / lastfm_meta.py

#source #python

> path: phi/meta/lastfm_meta.py  
> ext: .py  

---

# phi / meta / lastfm_meta.py

phi.meta.lastfm_meta — read metadata FROM Last.fm (separate from scrobbling).

Reads track info, user tags, and similar tracks from the Last.fm API.
Uses only the public read API — no session key or scrobbling credentials needed.
All calls are over plain urllib (no extra deps).

Data returned per track
-----------------------
listeners       int     Global unique listener count
playcount       int     Total global scrobble count
tags            list[str]  Top community tags (max 5) — rich genre / mood labels
wiki_summary    str     Short Wikipedia-style blurb (first sentence only)
similar_trac

Defines: LastFmTrackInfo, _api_get, _strip_html, fetch_track_info, fetch_similar_tracks, fetch_artist_tags, get_lastfm_api_key, as_annotation_dict, top_tag

---

## Semantic links

→ [[tools-enrich-c7]]
→ [[engine-phi-session]]
→ [[scripts-embed-tracks]]
→ [[MEMORY]]
→ [[engine-phi-player]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-watch-lastfm-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-track-store-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-spotify-client-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-batch-extractor-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-reader-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
