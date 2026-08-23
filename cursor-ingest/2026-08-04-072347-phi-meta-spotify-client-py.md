# phi / meta / spotify_client.py

#source #python

> path: phi/meta/spotify_client.py  
> ext: .py  

---

# phi / meta / spotify_client.py

phi.meta.spotify_client — Spotify track search + audio features.

Uses the Client Credentials OAuth flow — no user login required.
Provides exact numerical audio features that replace the BPM-bucketing
heuristics used by EnergyModel and MoodModel.

Audio features returned per track
----------------------------------
acousticness    float  0–1  Confidence the track is acoustic
danceability    float  0–1  How suitable for dancing (rhythm + beat stability)
energy          float  0–1  Perceptual intensity (loud + fast → high energy)
instrumentalness float 0–1  Predicts absence of vocals (>0.5 = li

Defines: AudioFeatures, SpotifyTrack, _RateLimiter, SpotifyClient, build_spotify_client, mood_tag, key_str, as_annotation_dict, as_meta_dict, as_annotation_dict, __init__, wait, __init__, available, _in_backoff, _set_backoff, search_by_isrc, enrich_track_by_isrc, search_track, get_audio_features, enrich_track, _parse_track, _fetch_art

---

## Semantic links

→ [[auth]]
→ [[index]]
→ [[fetcher]]
→ [[pipeline-sources-youtube-music]]
→ [[mcp-server]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-library-py]]
→ [[cursor-ingest/2026-08-04-072347-spotify-pipeline-auth-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-core-spotify-importer-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-track-store-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-spotify-bulk-enrich-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
