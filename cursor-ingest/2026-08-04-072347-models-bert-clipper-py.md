# models / bert_clipper.py

#source #python

> path: models/bert_clipper.py  
> ext: .py  

---

# models / bert_clipper.py


BERTClipper — lightweight numpy attention encoder (perpetual pretraining).

Architecture (ARCHITECTURE LOCKED — pow.md):

    Sits above SSMCore in the Octopus Tracer pipeline.

    Emits:
        H         ∈ ℝ^(N×d)   node embeddings  → SSMCore.tick() input
        tau       ∈ ℝ⁺        temperature       → SCUP cosine scaling
        lora_proj ∈ ℝ^(d×r)   projection slice  → LoRA sucker inheritance at spawn

    Layer structure (n_layers=2, n_heads=4, d_head=d//n_heads):
        embed    : X_raw (N×d_in) → X_emb (N×d)  W_emb (d_in×d) + b_emb (d)
        per layer:
            self-attention 

Defines: _AttnLayer, BERTClipper, __init__, _layer_norm, _softmax, _gelu, _softplus, _mhsa, _block, encode, update, n_params, __repr__

---

## Semantic links

→ [[models-bert-clipper]]
→ [[models-suckers]]
→ [[models-init]]
→ [[engine-tracer-daemon]]
→ [[models-ssm]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-models-bert-clipper-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-bert-clipper-py]]
→ [[cursor-ingest/2026-08-04-072347-models-suckers-py]]
→ [[cursor-ingest/2026-08-04-072347-source-models-index-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-bert-encoder-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
