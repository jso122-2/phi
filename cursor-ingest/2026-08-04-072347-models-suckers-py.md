# models / suckers.py

#source #python

> path: models/suckers.py  
> ext: .py  

---

# models / suckers.py


LoRA Sucker Layer — unbounded elastic LoRA for OctopusTracer.

Architecture (LOCKED — pow.md):

    Spawn condition:  ‖R(u)‖ > θ  → spawn sucker on relevant arm
    Sucker init:      inherits BERT clipper weights at spawn (or random A)
                      B = 0  → output is zero at spawn
    Specialisation:   updates on local subgraph neighbourhood

LoRA structure:
    A ∈ ℝ^(d×r)   — fixed at spawn (initialised from projection weights or random)
    B ∈ ℝ^(r×d)   — zero at spawn; updated by gradient steps
    forward(x) = x @ A @ B    ∈ ℝ^(N×d)

Because B=0 at init:  output = x @ A @ 0 = 0

Defines: LoRASucker, SpawnEvent, SuckerPool, __init__, forward, update, is_active, __repr__, __init__, maybe_spawn, forward_all, n_live, __repr__

---

## Semantic links

→ [[models-suckers]]
→ [[models-init]]
→ [[models-octopus-head]]
→ [[models-bert-clipper]]
→ [[engine-cairrn-tracer-daemon]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-models-suckers-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-suckers-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-lora-sucker-py]]
→ [[cursor-ingest/2026-08-04-072347-models-bert-clipper-py]]
→ [[cursor-ingest/2026-08-04-072347-models-init-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
