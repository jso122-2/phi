# phi / data / dataset.py

#source #python

> path: phi/data/dataset.py  
> ext: .py  

---

# phi / data / dataset.py


PyTorch Dataset and batching utilities for SambaGNN training.

GraphBatch holds precomputed node embeddings + ordered neighborhood sequences
so that the GNN forward pass doesn't have to re-encode text every step.


Defines: GraphBatch, ObsidianGraphDataset, to, __init__, set_hop_radius, _build_neighbor_cache, _build_link_pairs, _sample_negatives, __len__, __getitem__, get_batch

---

## Semantic links

→ [[scripts-train]]
→ [[scripts-samba-mcp-server]]
→ [[graph-source-extractor]]
→ [[graph-node]]
→ [[scripts-pretrain-loop]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-data-unified-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-samba-layer-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-samba-gnn-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-symbol-node-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
