# phi_config.example.yaml

#doc #yaml

> path: phi_config.example.yaml  
> ext: .yaml  

---

# phi_config.example.yaml — copy to phi_config.yaml and fill in your values

meta_enrichment:
  # AcoustID key is optional — without it the daemon still runs Discogs, Deezer,
  # Lyrics, Spotify, Last.fm, and Consensus enrichment.
  # Get a free key at https://acoustid.org/login
  acoustid_api_key: ""
  mb_user_agent: "phi/0.3.0 (your@email.com)"
  confidence_threshold: 0.70    # auto-accept AcoustID match above this score
  write_back_enabled: true      # write enriched tags back to audio files
  inter_track_seconds: 1.0      # sleep between tracks to avoid hammering APIs
  pause_during_playback: true   # if false, enrichment runs even while audio plays

---

## Semantic links

→ [[auth]]
→ [[config]]
→ [[engine-coherence-daemon]]
→ [[obsidian-exporter]]
→ [[index]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-config-yaml]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-track-store-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-spotify-client-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-deezer-client-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
