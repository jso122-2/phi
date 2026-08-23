# psspps / embedder.py

#source #python

> path: psspps/embedder.py  
> ext: .py  

---

# psspps / embedder.py


MiniLM embedder — ONNX runtime, zero torch dependency.

Model:  sentence-transformers/all-MiniLM-L6-v2
        22 M params, 384-dim output, cosine-similarity friendly.

Weight cache:  <vault>/.cache/minilm/          (fastembed-managed, git-ignored)
Embedding cache: <vault>/.cache/embeddings.npz  (keyed by doc-content hash)

On first call the model is downloaded once (~23 MB) and stored in the vault
cache directory.  Subsequent calls hit disk only.


Defines: _get_model, embed, embed_docs, cosine_matrix, _content_hash

---

## Semantic links

→ [[psspps-embedder]]
→ [[scripts-embed-tracks]]
→ [[psspps-traverser]]
→ [[psspps-pipeline]]
→ [[models-bert-clipper]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-psspps-embedder-md]]
→ [[cursor-ingest/2026-08-04-072347-scripts-embed-tracks-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-embed-tracks-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-clap-model-py]]
→ [[cursor-ingest/2026-08-04-072347-source-scripts-index-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
