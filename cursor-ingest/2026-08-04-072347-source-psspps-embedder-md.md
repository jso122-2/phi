# source / psspps-embedder.md

#doc #md

> path: source/psspps-embedder.md  
> ext: .md  

---

# psspps/embedder

#code #module #psspps #code

> source_path: psspps/embedder.py  
> package: psspps  
> module: psspps/embedder  
> hub: CODE  
> created_ts:   

---

**Package:** `psspps`  
**Module:** `psspps/embedder`  
**Source:** `psspps/embedder.py`

MiniLM embedder — ONNX runtime, zero torch dependency.

Model:  sentence-transformers/all-MiniLM-L6-v2
        22 M params, 384-dim output, cosine-similarity friendly.

Weight cache:  <vault>/.cache/minilm/          (fastembed-managed, git-ignored)
Embedding cache: <vault>/.cache/embeddings.npz  (keyed by doc-content hash)

On first call the model is downloaded once (~23 MB) and stored in the vault
cache directory.  Subsequent calls hit disk only.

## API

- `def _get_model`
- `def embed` — Embed a sequence of strings → float32 array of shape (N, 384).
- `def embed_docs` — Embed a list of VaultDoc dicts, using the on-disk cache when valid.
- `def cosine_matrix` — Compute cosine similarities between a single query vector and a corpus.
- `def _content_hash`

---

## Semantic links

→ [[2026-07-17T01-33-09Z-CLAPProjection and PhiGraph — DAWN bridge layer]]
→ [[psspps]]
→ [[psspps]]
→ [[CODE]]
→ [[CODE]]

## Related notes

→ [[source/psspps-init]]
→ [[source/scripts-embed-tracks]]
→ [[source/psspps-pipeline]]
→ [[source/psspps-traverser]]
→ [[source/models-bert-clipper]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[psspps-index]]
→ [[psspps-pipeline]]
→ [[psspps-retriever]]
→ [[psspps-init]]
→ [[psspps-router]]
→ [[mcp-server-tools-search]]

---

## Semantic links

→ [[psspps-embedder]]
→ [[scripts-embed-tracks]]
→ [[psspps-retriever]]
→ [[scripts-run]]
→ [[mcp-server-main]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-psspps-embedder-py]]
→ [[cursor-ingest/2026-08-04-072347-source-psspps-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-psspps-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-embed-tracks-md]]
→ [[cursor-ingest/2026-08-04-072347-source-mcp-server-tools-vpn-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
