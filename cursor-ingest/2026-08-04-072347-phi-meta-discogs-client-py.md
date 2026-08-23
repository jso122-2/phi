# phi / meta / discogs_client.py

#source #python

> path: phi/meta/discogs_client.py  
> ext: .py  

---

# phi / meta / discogs_client.py

phi.meta.discogs_client — Discogs release metadata.

Fetches pressing info, community market data, styles, and production credits
that are not available from MusicBrainz or Spotify.

Data returned per release
--------------------------
year              int     Release year (this pressing)
master_year       int     Original release year (from master resource, if found)
country           str     Release country (e.g. "US", "UK", "Europe")
format            str     Primary format: "Vinyl", "CD", "Digital", "Cassette", …
format_details    list    Sub-descriptions: ["LP", "Album", "Stereo", "180g"

Defines: DiscogsRelease, _RateLimiter, DiscogsClient, build_discogs_client, desirability, as_annotation_dict, __init__, wait, __init__, available, search_release, fetch_release, _get, _parse_release

---

## Semantic links

→ [[pipeline-fetcher-models]]
→ [[fetcher]]
→ [[tools-enrich-c7]]
→ [[mcp-server]]
→ [[pipeline-sources-youtube-music]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-meta-track-store-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-library-py]]
→ [[cursor-ingest/2026-08-04-072347-source-pipeline-fetcher-models-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-playlist-store-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-library-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
