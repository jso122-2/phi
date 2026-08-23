# pipeline / sources / soundcloud.py

#source #python

> path: pipeline/sources/soundcloud.py  
> ext: .py  

---

# pipeline / sources / soundcloud.py

pipeline.sources.soundcloud — SoundCloud fallback source.

Searches SoundCloud via yt-dlp's scsearch: extractor.  Useful for
tracks that are unavailable on YouTube Music / YouTube (regional blocks,
copyright takedowns, etc.).

Note: config.yaml sets soundcloud.use_proxy=false because SoundCloud
blocks SOCKS5 in some regions.  The proxy arg is accepted but defaults
to None here to honour that setting at the call site.


Defines: SoundCloudSource, download

---

## Semantic links

→ [[pipeline-sources-soundcloud]]
→ [[pipeline-sources-internet-archive]]
→ [[pipeline-sources-youtube]]
→ [[pipeline-sources-youtube-music]]
→ [[pipeline-sources-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-soundcloud-md]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-internet-archive-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-youtube-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-sources-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-sources-youtube-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
