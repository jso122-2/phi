# source / engine-gate.md

#doc #md

> path: source/engine-gate.md  
> ext: .md  

---

# engine/gate

#code #module #engine #code

> source_path: engine/gate.py  
> package: engine  
> module: engine/gate  
> hub: CODE  
> created_ts:   

---

**Package:** `engine`  
**Module:** `engine/gate`  
**Source:** `engine/gate.py`

Coherence gate for OctopusTracer arms.

Formula (ARCHITECTURE LOCKED — pow.md):

    coherence = exp(−steps / τ_cairrn)

    if coherence < W(1)  →  arms suppress write, read-only pass
    if coherence ≥ W(1)  →  full arm authority, Samba MCP live

Threshold derivation:
    W(1) = abs(NEG_EXP_FIXED_POINT) = 𝒜_χ / e ≈ 0.5671
    Identity: exp(−W(1)) = W(1) — coherence at HOME equals the threshold.

The gate is stateless — call gate_coherence() with (steps, tau) each tick.

## API

- `def gate_coherence` — Compute arm coherence score.
- `def is_coherent` — True when arms have full write authority.
- `def gate_pass` — Convenience: compute coherence and gate flag in one call.

## Internal imports

`sims.attractors`

---

## Semantic links

→ [[2026-07-16-011935-vault-coherence-engine]]
→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]
→ [[2026-03-06-083848-2026-03-06t19-38-49-304-11-00]]
→ [[MATH]]
→ [[2025-05-26-210158-conciousness-threshold-start]]

## Related notes

→ [[source/engine-init]]
→ [[source/engine-cairrn-dispatch]]
→ [[source/engine-cairrn-bridge]]
→ [[source/engine-coherence-gate]]
→ [[source/engine-cairrn-tracer-daemon]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[engine-index]]
→ [[engine-cairrn-scheduler]]
→ [[engine-init]]
→ [[engine-coherence-gate]]
→ [[engine-main]]
→ [[engine-health-log]]

---

## Semantic links

→ [[engine-gate]]
→ [[engine-init]]
→ [[engine-coherence-daemon]]
→ [[engine-cairrn-dispatch]]
→ [[engine-coherence-gate]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-engine-gate-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-init-md]]
→ [[cursor-ingest/2026-08-04-072347-engine-init-py]]
→ [[cursor-ingest/2026-08-04-072347-source-engine-coherence-gate-md]]
→ [[cursor-ingest/2026-08-04-072347-source-models-octopus-head-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
