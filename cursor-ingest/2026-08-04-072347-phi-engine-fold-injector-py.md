# phi / engine / fold_injector.py

#source #python

> path: phi/engine/fold_injector.py  
> ext: .py  

---

# phi / engine / fold_injector.py

phi.engine.fold_injector — inject track fold-bits into the shared harmonic index.

Each fold bit encodes a right (1) or left (0) turn on the dragon curve and maps
directly onto one of the 8 harmonic shards:

    bit=1  →  inject  +ALPHA * weight  (right attractor side)
    bit=0  →  inject  −ALPHA * weight  (left attractor side)

The injection is additive (not a reset), and one local-diffusion propagation
step follows each call so κ=0.15 coupling has a chance to smooth the ring
before the next track arrives.


Defines: FoldInjector, __init__, inject, state, __repr__

---

## Semantic links

→ [[sims-harmonic]]
→ [[mcp-server-tools-harmonic]]
→ [[harmonic-index]]
→ [[harmonic-index]]
→ [[engine-cairrn-scheduler]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-sims-harmonic-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-models-dragon-curve-py]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-init-py]]
→ [[cursor-ingest/2026-08-04-072347-harmonic-index-md]]
→ [[cursor-ingest/2026-08-04-072347-attractors-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
