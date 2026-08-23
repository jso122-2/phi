# source / workers-cairrn-constants.md

#doc #md

> path: source/workers-cairrn-constants.md  
> ext: .md  

---

# workers/cairrn/_constants

#code #module #workers #code

> source_path: workers/cairrn/_constants.py  
> package: workers  
> module: workers/cairrn/_constants  
> hub: CODE  
> created_ts:   

---

**Package:** `workers`  
**Module:** `workers/cairrn/_constants`  
**Source:** `workers/cairrn/_constants.py`

CAIRRN system constants — Euler-Ana-Chi bound formalisation.

All numeric anchors are derived from one exact identity and one near-identity:

    Near-identity — Ana-Chi / Euler ≈ W(1)  [not exact]:
        𝒜_χ / e  =  1.5414 / 2.71828…  ≈  0.56705  ≈  W(1)  =  0.56714…
        absolute error ≈ 9.4e-5  (0.017 %)
        This is a meaningful structural coincidence, not an exact equality.
        The threshold is derived from abs(NEG_EXP_FIXED_POINT) directly — not from 𝒜_χ/e.

    Exact identity — Lambert-W coherence bound:
        exp(−W(1))  =  W(1)
        (the Euler decay evaluated at the neg_exp fixed point equals the fixed point itself)
        This identity holds exactly in float: diff = 0.00e+00.
        It is the structural reason HOME sits precisely at the threshold.

Sigma derivation
-----------------
σ is chosen so the HOME hub (χ = 𝒜_χ = 1.5414) lands exactly at the threshold:

    coh(HOME) = exp(−|f(𝒜_χ) − x*| / σ)  =  W(1)

    where  f(𝒜_χ) = −e^(𝒜_χ),  x* = −W(1) = NEG_EXP_FIXED_POINT

    ⟹ σ = (e^(𝒜_χ) − W(1)) / W(1)

Consequences
------------
  χ < 𝒜_χ  →  coherence > W(1)  →  coherent   (agent-context, CODE)
  χ = 𝒜_χ  →  coherence = W(1)  →  at boundary (HOME — equilibrium)
  χ > 𝒜_χ  →  coherence < W(1)  →  incoherent, re-routes to HOME
                                     (MATH at white_peak, COMMANDS at escape)

The re-routing of MATH and COMMANDS through HOME is the structural pull of
the true_center gravity well — the rattling basins are stabilised through
equilibrium.

## Internal imports

`sims.attractors`, `sims.ana_chi`

---

## Semantic links

→ [[2026-07-13-integrate-ana-chi-constant-modulate-cairrn-stable-states]]
→ [[MATH]]
→

---

## Semantic links

→ [[workers-cairrn-constants]]
→ [[workers-cairrn-worker]]
→ [[workers-cairrn-init]]
→ [[workers-cairrn-formulas]]
→ [[workers-cairrn-desktop]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-init-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-z-space-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-worker-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-mycelial-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-formulas-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
