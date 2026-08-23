# source / models-bert-clipper.md

#doc #md

> path: source/models-bert-clipper.md  
> ext: .md  

---

# models/bert_clipper

#code #module #models #math

> source_path: models/bert_clipper.py  
> package: models  
> module: models/bert_clipper  
> hub: MATH  
> created_ts:   

---

**Package:** `models`  
**Module:** `models/bert_clipper`  
**Source:** `models/bert_clipper.py`

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
            self-attention : W_Q, W_K, W_V, W_O (d×d each) + residual + LayerNorm
            FFN            : W_ff1 (d×d_ff) + W_ff2 (d_ff×d) + residual + LayerNorm
        tau head           : softplus(mean(H) @ w_tau)

    lora_proj = W_O[:, :lora_rank] from the last attention layer → (d, lora_rank)
    Passed to LoRASucker(A_init=lora_proj) at spawn for BERT-weight inheritance.

    Perpetual pretraining (denoising autoencoder):
        update(X, lr, noise_std)
            — adds Gaussian noise, reconstructs X via W_out,
              computes MSE, clips global gradient norm, updates W_emb + W_out.

Parameter budget (d=256, n_layers=2, n_heads=4, d_ff=1024):
    embed     : 256×256 + 256  =  65,792
    2 layers  : 2 × (4×256×256 + 2×256 + 256×1024 + 1024 + 1024×256 + 256 + 2×256)
              ≈ 2 × 786,432     = 1,572,864
    W_out     : 256×256        =  65,536
    w_tau     : 256            =      256
    Total                      ≈ 1.7M   (pow.md: "lives above — not counted")

## API

- `class _AttnLayer`
- `class BERTClipper` — Multi-head self-attention encoder with perpetual denoising pretraining.

---

## Semantic links

---

## Semantic links

→ [[models-bert-clipper]]
→ [[models-init]]
→ [[mcp-server-tools-phi-clip]]
→ [[scripts-pretrain-loop]]
→ [[models-regression]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-models-bert-clipper-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-bert-clipper-py]]
→ [[cursor-ingest/2026-08-04-072347-source-models-index-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-bert-encoder-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-gemini-clipper-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
