# phi / meta / art_spider.py

#source #python

> path: phi/meta/art_spider.py  
> ext: .py  

---

# phi / meta / art_spider.py

phi.meta.art_spider — background daemon that fills missing album art.

Crawl strategy (in order, stops on first hit per track):
    1. Deezer album cover  — free, no auth, 250 × 250 JPEG
    2. CoverArtArchive     — free, no auth, via release_mbid from annotations
    3. Folder scan         — cover.jpg / cover.png / folder.jpg in same dir

The spider runs in a daemon thread and respects rate limits already built
into DeezerClient and MBClient.  It is intentionally slow (≤ 1 resolved
track / second) so it never competes with playback I/O.

Public API
----------
    spider = ArtSpider(library, c

Defines: ArtSpider, get_art_spider, __init__, start, stop, kick, status, _run, _fetch_art, _deezer_art, _caa_art, _folder_art, _patch

---

## Semantic links

→ [[tools-enrich-c7]]
→ [[engine-prefeed-shuffle]]
→ [[graph-node]]
→ [[tools-fix-dead-links]]
→ [[engine-rsync-bridge]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-meta-art-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-mb-client-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-track-store-py]]
→ [[cursor-ingest/2026-08-04-072347-tools-enrich-c7-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-enrich-daemon-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
