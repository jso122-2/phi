# phi / gnn / lora_sucker.py

#source #python

> path: phi/gnn/lora_sucker.py  
> ext: .py  

---

# phi / gnn / lora_sucker.py


LoRA Sucker — dynamic low-rank adapter that spawns onto a gardening arm.

Each sucker is a rank-r LoRA correction applied additively to an arm's output:

    sucker(R) = (B @ A @ R.T).T  →  (N, D)

Where:
    A ∈ ℝ^(r × D)   — down-projection  (initialized from N(0, 1/r))
    B ∈ ℝ^(D × r)   — up-projection    (initialized to zero, so sucker starts silent)
    scale            — α / r  (LoRA scaling factor, α=1 by default)

Spawn rule:
    if ‖R(u)‖ > spawn_threshold for any node u → SuckerPool.maybe_spawn()
    new sucker optionally inherits A from BERT clipper's projection weights (clipped 

Defines: LoRASucker, SuckerPool, __init__, forward, param_count, __init__, maybe_spawn, forward, count, param_count, pressure_history

---

## Semantic links

→ [[models-suckers]]
→ [[2026-07-17T01-33-09Z-CLAPProjection and PhiGraph — DAWN bridge layer]]
→ [[models-arms]]
→ [[mcp-server-tools-sims]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-models-suckers-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-suckers-py]]
→ [[cursor-ingest/2026-08-04-072347-source-models-suckers-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-octopus-tracer-py]]
→ [[cursor-ingest/2026-08-04-072347-models-arms-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
