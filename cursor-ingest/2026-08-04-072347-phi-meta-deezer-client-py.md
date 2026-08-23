# phi / meta / deezer_client.py

#source #python

> path: phi/meta/deezer_client.py  
> ext: .py  

---

# phi / meta / deezer_client.py

phi.meta.deezer_client — Deezer track metadata (no auth required).

Uses the public Deezer API — no API key or OAuth needed.
Provides a BPM cross-reference, explicit flag, popularity rank, gain
offset (loudness normalisation target), and a 30-second preview URL.

Data returned per track
-----------------------
deezer_id       int     Deezer track ID
deezer_bpm      float   Deezer's own BPM estimate (cross-check against librosa)
deezer_gain     float   Gain offset in dB (Deezer's replay-gain-like value)
deezer_explicit bool    Explicit lyrics flag
deezer_rank     int     Popularity score (0 – ~

Defines: DeezerTrack, _RateLimiter, DeezerClient, get_deezer_client, as_annotation_dict, __init__, wait, __init__, search_track, _get, fetch_album_art_bytes, _parse_track, _score

---

## Semantic links

→ [[engine-phi-session]]
→ [[pipeline-fetcher-models]]
→ [[fetcher]]
→ [[mcp-server-tools-harmonic]]
→ [[index]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-meta-spotify-client-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-bpm-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-track-store-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-lastfm-meta-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-watch-enrich-daemon-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
