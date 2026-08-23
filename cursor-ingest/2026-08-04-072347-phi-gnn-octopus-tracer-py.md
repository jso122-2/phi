# phi / gnn / octopus_tracer.py

#source #python

> path: phi/gnn/octopus_tracer.py  
> ext: .py  

---

# phi / gnn / octopus_tracer.py


OctopusTracer — Obsidian-bound gardening transformer (≤4M params).

Two operating modes, selected by `soft_edge_mode`:

  SOFT EDGE MODE (default, recommended for autonomous operation)
  ─────────────────────────────────────────────────────────────
  No adjacency matrix required.  R is computed as a soft neighbourhood
  aggregation driven entirely by embedding similarity:

      S[u,v] = sigmoid( (ĥᵤ · ĥᵥ) / τ )     ← soft edge activation
      S.fill_diagonal_(0)                      ← no self-loops
      R = S @ H                                ← (N, D) neighbourhood summary

  High S → nod

Defines: TracerOutput, OctopusTracer, __init__, tau, _scup_cosine, _regression_pipeline, tick, reset_tick, coherence_score, write_gated, maybe_spawn_suckers, inject_temperature, forward, parameter_report, sucker_report, count

---

## Semantic links

→ [[models-octopus-head]]
→ [[engine-mycelial]]
→ [[engine-tracer-daemon]]
→ [[models-regression]]
→ [[models-suckers]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-phi-gnn-tracer-arms-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-gnn-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-mycelial-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-graph-phi-graph-py]]
→ [[cursor-ingest/2026-08-04-072347-engine-tracer-daemon-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
