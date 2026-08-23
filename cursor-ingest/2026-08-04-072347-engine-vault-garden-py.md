# engine / vault_garden.py

#source #python

> path: engine/vault_garden.py  
> ext: .py  

---

# engine / vault_garden.py


engine.vault_garden — Obsidian vault graph → TracerDaemon one cycle.

This is the runtime entry point for gardening-mode OctopusTracer operation.
Instead of music-library tracks (PhiOrchestrator), the input is the vault
knowledge graph — every VaultNode is a graph vertex.

Pipeline
--------
  1. load_vault()            →  list[VaultNode]  (N nodes)
  2. embed_nodes(nodes)      →  X (N, d_embed)   fastembed text embeddings
  3. build_adjacency(nodes)  →  A (N, N)         wikilink edges (directed → symmetric)
  4. project(X, d_model)     →  X_proj (N, d)    random-projection to d_model dims
  5

Defines: build_adjacency, embed_nodes, project_embeddings, _node_text, VaultGarden, __init__, run_cycle, daemon, tick, samba_dir, __repr__

---

## Semantic links

→ [[engine-vault-garden]]
→ [[graph-node]]
→ [[graph-ingestion]]
→ [[engine-vault-writer]]
→ [[engine-cairrn-tracer-daemon]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-engine-vault-garden-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-gnn-py]]
→ [[cursor-ingest/2026-08-04-072347-graph-node-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-init-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
