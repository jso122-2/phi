# phi / utils / replay.py

#source #python

> path: phi/utils/replay.py  
> ext: .py  

---

# phi / utils / replay.py


ReplayBuffer for Perpetual Pretraining
Stores graph snapshots (node embeddings + edge topology) and mixes old
experience with new vault observations during perpetual training.

Design:
    - Ring buffer of fixed capacity (in snapshot slots)
    - Each slot = a GraphSnapshot (node_emb, edge_index, edge_weight, metadata)
    - Sampling strategy: recent-biased exponential decay so new notes
      are seen more often than old ones, but old structure is never forgotten
    - Priority queue within each slot for curriculum: harder examples sampled more

Two use cases:
    1. Pretraining on synthetic

Defines: GraphSnapshot, ReplayBuffer, generate_synthetic_snapshot, prefill_buffer_synthetic, to, num_nodes, num_edges, __init__, add, sample, update_priority, __len__, vault_count, synthetic_count

---

## Semantic links

→ [[graph-init]]
→ [[MEMORY]]
→ [[graph-logger]]
→ [[graph-ingestion]]
→ [[engine-vault-garden]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-vault-garden-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-init-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-ingestion-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-utils-perpetual-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-coherence-daemon-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
