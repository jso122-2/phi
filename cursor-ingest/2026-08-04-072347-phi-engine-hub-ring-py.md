# phi / engine / hub_ring.py

#source #python

> path: phi/engine/hub_ring.py  
> ext: .py  

---

# phi / engine / hub_ring.py

phi.engine.hub_ring — Music-domain harmonic hub/spoke ring for phi.

A dedicated 8-shard HarmonicIndex whose shards map to music-semantic domains,
separate from both the MCP station-hub ring and the CAIRRN operational ring.

Hub layout (shard → basin centre = k·α, α=1.96):
    shard 0   1.96   PLAYBACK   live track state, queue position
    shard 1   3.92   ENERGY     tempo, loudness, valence energy blend
    shard 2   5.88   MOOD       emotional arc, danceability
    shard 3   7.84   GENRE      style, speechiness, acousticness
    shard 4   9.80   ARTIST     artist / album context in vault
  

Defines: HubInjectionRecord, PhiHubRing, __init__, inject, inject_track_features, modulate_kappa, inject_topology, propagate, activations, active_hubs, active_spoke_queries, on_track_load, state, reset, injection_log

---

## Semantic links

→ [[harmonic-index]]
→ [[PLAYBACK]]
→ [[harmonic-index]]
→ [[mcp-server-tools-harmonic]]
→ [[GENRE]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-sims-harmonic-md]]
→ [[cursor-ingest/2026-08-04-072347-harmonic-index-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-cairrn-bridge-py]]
→ [[cursor-ingest/2026-08-04-072347-temporal-index-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-vault-context-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
