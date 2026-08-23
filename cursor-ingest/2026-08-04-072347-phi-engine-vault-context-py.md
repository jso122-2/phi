# phi / engine / vault_context.py

#source #python

> path: phi/engine/vault_context.py  
> ext: .py  

---

# phi / engine / vault_context.py

phi.engine.vault_context — PSSPPS bridge for Obsidian retrieval.

Queries the Obsidian vault (via the PSSPPS pipeline in Spotify-Rip) whenever
a new track loads.  The retrieval result is converted to a single [0, 1]
signal and injected into the CAIRRN agent-context hub and the music hub ring.

Pipeline (extended)
───────────────────
  track title + artist  +  audio features from meta
        │                         │
        │                         ▼
        │              PhiHubRing.on_track_load(features)
        │                         │
        │              ring.active_spoke_querie

Defines: _ensure_psspps, _signal, query_async, _extract_features, get_hub_ring, query_async_with_ring, _worker, _worker

---

## Semantic links

→ [[VAULT]]
→ [[ARTIST]]
→ [[engine-vault-garden]]
→ [[mcp-server-vault-hub]]
→ [[PLAYBACK]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-mcp-server-vault-hub-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-vault-garden-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-hub-ring-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-meta-spotify-client-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
