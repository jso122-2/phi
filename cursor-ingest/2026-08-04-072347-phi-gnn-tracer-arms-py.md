# phi / gnn / tracer_arms.py

#source #python

> path: phi/gnn/tracer_arms.py  
> ext: .py  

---

# phi / gnn / tracer_arms.py


Octopus Tracer — 8 Gardening Arms (MLP task heads).

All arms share the same input: R ∈ ℝ^(N × D)
The regression matrix R is computed upstream by OctopusTracer:
    R = arccos(scup_cos(H)) @ (L̅ · H)

where:
    H   = node embeddings from SambaGNN  (N, D)
    L̅   = complement graph Laplacian     (N, N)

Each arm is a 2-layer MLP preceded by an OctopusAttentionHead.
The attention head implements the locked formula:

    v_d  = β̂(R) × ‖R(u)‖               ← direction beta × drift derivative
    A_vd = Ā̅ × v_d                       ← scaled complement adjacency
    attn = softmax(A_vd @ Ā̅ᵀ −

Defines: OctopusAttentionHead, GardeningArm, _ScalarArm, PruneArm, RankArm, ResurfaceArm, SproutArm, _PairwiseArm, GraftArm, MergeArm, ClusterArm, TagArm, __init__, fs, forward, __init__, attend, maybe_spawn_sucker, sucker_correction, __init__, forward, __init__, temp, forward, __init__, temp, forward, __init__, forward

---

## Semantic links

→ [[models-octopus-head]]
→ [[models-arms]]
→ [[models-regression]]
→ [[models-init]]
→ [[engine-tracer-daemon]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-models-arms-py]]
→ [[cursor-ingest/2026-08-04-072347-source-models-arms-md]]
→ [[cursor-ingest/2026-08-04-072347-models-regression-py]]
→ [[cursor-ingest/2026-08-04-072347-models-octopus-head-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-gnn-octopus-tracer-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
