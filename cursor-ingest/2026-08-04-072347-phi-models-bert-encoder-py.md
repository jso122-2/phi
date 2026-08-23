# phi / models / bert_encoder.py

#source #python

> path: phi/models/bert_encoder.py  
> ext: .py  

---

# phi / models / bert_encoder.py

phi.models.bert_encoder — phi-local BERT clipping encoder with offline cache.

On first use the model is fetched from HuggingFace Hub and pinned to
~/.phi/bert_encoder/<model_slug>/.  Every subsequent load reads from disk —
no network calls, no Hub warnings.

Consumers inside phi always import from here.  The samba-gnn top-level
models/encoder.py is used only by the GNN training loop and is unaffected.


Defines: _model_slug, _local_path, ensure_local, BERTClippingEncoder, __init__, _encode_raw, forward, encode_single, trainable_params

---

## Semantic links

→ [[models-bert-clipper]]
→ [[scripts-embed-tracks]]
→ [[engine-phi-session]]
→ [[2026-07-17T01-33-09Z-CLAPProjection and PhiGraph — DAWN bridge layer]]
→ [[models-init]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-gnn-encoder-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-samba-gnn-py]]
→ [[cursor-ingest/2026-08-04-072347-source-models-bert-clipper-md]]
→ [[cursor-ingest/2026-08-04-072347-models-bert-clipper-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-bert-clipper-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
