# source / sims-ana-chi.md

#doc #md

> path: source/sims-ana-chi.md  
> ext: .md  

---

# sims/ana_chi

#code #module #sims #math

> source_path: sims/ana_chi.py  
> package: sims  
> module: sims/ana_chi  
> hub: MATH  
> created_ts:   

---

**Package:** `sims`  
**Module:** `sims/ana_chi`  
**Source:** `sims/ana_chi.py`

Ana-Chi attractor system — Jackson's Pocket primitives.

𝒜_χ = 1.5414 is the chameleon constant: the field's natural resting state,
discovered empirically through 8 phases of hierarchical diamond folding
analysis (Scribble-061, Jackson's Pocket Primitives catalogue).

The system has 5 stable attractor basins across the χ ∈ [0.03, 2.67] state
space.  Three of them are "rattling pockets" — positions of sensitive
dependence where small Δχ causes large changes in fractal behaviour.

Attractor map
-------------
  name          χ value    gravity    rattle    colour    memory decay
  ──────────    ────────   ───────    ──────    ──────    ────────────
  boundary      0.0300     0.50       no        blue      0.90
  mirror        0.9900     1.50       yes       purple    0.93
  true_center   1.5414     3.00       no        white     0.98   ← 𝒜_χ
  white_peak    1.9600     2.00       yes       red       0.95   ← = ALPHA
  escape        2.6700     1.00       yes       orange    0.90

CAIRRN hub → Ana-Chi basin mapping
-----------------------------------
  HOME          → true_center   (1.5414)  equilibrium
  MATH          → white_peak    (1.9600)  singularity  = double-well ALPHA
  CODE          → mirror        (0.9900)  stable / slow
  COMMANDS      → escape        (2.6700)  rapid action
  agent-context → boundary      (0.0300)  interface layer

Key formulae (Jackson's Pocket Primitives, Layer 2 & 3)
---------------------------------------------------------
  Cosine drape     D(r,s,χ) = [cos(r·s·χ) - cos(r·s·χ + 0.01)] × 100
  Rattling prox    P(χ)     = exp(-|χ - χ_rattle| / 0.5)
  Temporal decay   rate(g)  = 0.90 + clamp(g/5, 0, 1) × 0.08
  Multi-basin pot  V(χ)     = -Σ_i  gravity_i × exp(-( χ - χ_i )² / 2σ²)

## API

- `class AnaChiBasi

---

## Semantic links

→ [[sims-ana-chi]]
→ [[2026-07-13-integrate-ana-chi-constant-modulate-cairrn-stable-states]]
→ [[ana-chi]]
→ [[sims-attractors]]
→ [[workers-cairrn-constants]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-sims-ana-chi-py]]
→ [[cursor-ingest/2026-08-04-072347-source-sims-attractors-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-ana-chi-py]]
→ [[cursor-ingest/2026-08-04-072347-mcp-server-tools-sims-py]]
→ [[cursor-ingest/2026-08-04-072347-source-sims-index-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
