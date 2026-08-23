# source / models-ssm.md

#doc #md

> path: source/models-ssm.md  
> ext: .md  

---

# models/ssm

#code #module #models #math

> source_path: models/ssm.py  
> package: models  
> module: models/ssm  
> hub: MATH  
> created_ts:   

---

**Package:** `models`  
**Module:** `models/ssm`  
**Source:** `models/ssm.py`

SSM Core — tick-synchronised state-space model for OctopusTracer.

Architecture (LOCKED — pow.md):

    Takes node embeddings X ∈ ℝ^(N×d) at each tick.
    Emits:
      H   ∈ ℝ^(N×d)  — hidden state per node, updated each tick
      tau ∈ ℝ⁺       — temperature (used in SCUP cosine)

Parameter budget target: ~900K at d=256.

Layer structure (4 SSM layers):
  Per layer: A (d×d) + B (d×d) + C (d×d) + bias_a (d) + bias_c (d)
  Params per layer:  3 × d² + 2d  = 3×65536 + 512 = 197,120
  4 layers:          788,480
  tau (1 scalar):    1
  Total:             ~788K  (target ≤ 900K  ✓)

State update per layer (left-to-right through the sequence):
    h = tanh(x @ B.T + h_prev @ A.T + bias_a)
    y = h @ C.T + bias_c
    x (next layer) = y

Final output: H = y_last  (N×d),  tau = softplus(log_tau)

## API

- `class SSMLayerParams` — Weight tensors for one SSM layer.
- `class SSMCore` — Multi-layer numpy SSM core.

---

## Semantic links

→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]
→ [[2025-05-24-025238-dawn-build-sprint-due-8-30-pm-aest]]
→ [[2025-05-27-174633-2025-05-28t03-46-33-990-10-00]]
→ [[2025-05-27-154538-dawns-10-pillars-for-agi]]
→ [[live-state]]

## Related notes

→ [[source/engine-tracer-daemon]]
→ [[source/models-octopus-head]]
→ [[source/models-regression]]
→ [[source/engine-gate]]
→ [[source/models-init]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[models-init]]
→ [[models-index]]
→ [[models-regression]]
→ [[models-arms]]
→ [[index]]
→ [[models-octopus-head]]

---

## Semantic links

→ [[models-ssm]]
→ [[models-init]]
→ [[models-octopus-head]]
→ [[models-regression]]
→ [[models-bert-clipper]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-models-ssm-py]]
→ [[cursor-ingest/2026-08-04-072347-source-models-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-models-octopus-head-md]]
→ [[cursor-ingest/2026-08-04-072347-source-models-regression-md]]
→ [[cursor-ingest/2026-08-04-072347-source-models-arms-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
