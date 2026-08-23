# phi / gnn / encoder.py

#source #python

> path: phi/gnn/encoder.py  
> ext: .py  

---

# phi / gnn / encoder.py


Encoder module for the Samba GNN.

Classes:
    BERTClippingEncoder   Frozen 2-layer BERT for prose / markdown text.
    CodeBERTEncoder       Frozen CodeBERT (clipped) for Python / JS symbols.
    DualEncoder           Routes SymbolNodes to the right encoder by language,
                          concatenates results in node_id order.

All encoders follow the same contract:
    forward(texts, device) -> Tensor(N, hidden_dim)

DualEncoder additionally accepts:
    forward_nodes(nodes, device) -> Tensor(N, hidden_dim)

The existing BERTClippingEncoder interface is unchanged — existing callers


Defines: BERTClippingEncoder, CodeBERTEncoder, DualEncoder, __init__, _freeze_bert, _encode_raw, forward, encode_single, trainable_params, __init__, _freeze_bert, _encode_raw, forward, encode_single, trainable_params, __init__, forward, forward_nodes, trainable_params

---

## Semantic links

→ [[models-bert-clipper]]
→ [[2026-07-17T01-33-09Z-CLAPProjection and PhiGraph — DAWN bridge layer]]
→ [[psspps-embedder]]
→ [[scripts-samba-mcp-server]]
→ [[scripts-embed-tracks]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-models-bert-encoder-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-samba-gnn-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-dataset-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-data-unified-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-samba-layer-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
