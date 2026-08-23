# source / engine-vault-garden.md

#doc #md

> path: source/engine-vault-garden.md  
> ext: .md  

---

# engine/vault_garden

#code #module #engine #code

> source_path: engine/vault_garden.py  
> package: engine  
> module: engine/vault_garden  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/vault_garden`  
**Source:** `engine/vault_garden.py`

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
  5. TracerDaemon.run_once(A, X_proj)
                             →  TracerSummary
                             →  SambaWriter vault writes (if coherence ≥ gate)

Usage
-----
    from engine.vault_garden import VaultGarden

    garden = VaultGarden(vault_root=Path("."))
    summary = garden.run_cycle()
    print(summary.as_dict())

The CAIRRN coherence gate inside TracerDaemon controls write authority.
On the first cycle (tick=0) coherence=1.0 → writes are live.
Arms will be suppressed on subsequent cycles until tick resets.

## API

- `def build_adjacency` — Build a symmetric boolean adjacency matrix from vault wikilinks.
- `def embed_nodes` — Embed vault node text using fastembed TextEmbedding (BAAI/bge-small-en-v1.5).
- `def project_embeddings` — Random orthogonal projection from d_in → d_out dimensions.
- `def _node_text` — Combine title + truncated body for embedding.
- `class VaultGarden` — Drives one OctopusTracer gardening cycle over the Obsidian vault graph.

## Internal imports

`graph.node`, `engine.tracer_daemon`, `engine.vault_writer`

---

## Semantic links

→ [[graph]]
→ [[graph]]
→ [[2026-07

---

## Semantic links

→ [[engine-vault-garden]]
→ [[engine-cairrn-tracer-daemon]]
→ [[engine-vault-writer]]
→ [[engine-coherence-daemon]]
→ [[scripts-spawn-tracer]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-vault-garden-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-vault-writer-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-tracer-daemon-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-coherence-daemon-md]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-init-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
