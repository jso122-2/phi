# source / workers-cairrn-formulas.md

#doc #md

> path: source/workers-cairrn-formulas.md  
> ext: .md  

---

# workers/cairrn/formulas

#code #module #workers #code

> source_path: workers/cairrn/formulas.py  
> package: workers  
> module: workers/cairrn/formulas  
> hub: CODE  
> created_ts:   

---

**Package:** `workers`  
**Module:** `workers/cairrn/formulas`  
**Source:** `workers/cairrn/formulas.py`

CAIRRN routing formula functions — pure math, no state.

These are the **routing / desktop** formulas: they operate on the
Ana-Chi attractor pipeline (modulation → sharding → coherence).

⚠️  VARIABLE NAME DISAMBIGUATION
Variables like `energy`, `nutrients`, and `pressure` appear in both this
file and in `mycelial.py`, but they play different structural roles:

  formulas.py (routing layer)          mycelial.py (metabolic layer)
  ─────────────────────────────────    ──────────────────────────────
  energy     = CAIRRN routing energy   energy   = node metabolic energy
  nutrients  = SCUP nutrient term      nutrients = softmax budget share
  pressure   = SCUP pressure metric    pressure  = cognitive demand input

Do NOT use formulas from this file to implement mycelial mechanics.
The metabolic substrate formula set lives exclusively in `mycelial.py`.

Organised by pipeline layer:
  Layer X — composite / constraint (cross-layer)
  Layer 1 — Ana-Chi Modulation
  Layer 2 — neg_exp Sharding
  Layer 3 — Coherence Enforcement
  Z-Space — active -Z spatial scoring (raw formula only)

## API

- `def f_constraint_var` — F_CONSTRAINT_VAR:  x_c = Lh / P − O
- `def f_forecast_score` — F_FORECAST_SCORE:  score = |(D − e) / x_c| · T · Δj
- `def f_cairrn_composite` — F_CAIRRN_COMPOSITE:  Ψ = |z+x|·|1−c| − |z+x|·|y−c| + Ti
- `def f_energy_weighted` — F_ENERGY_WEIGHTED:  EW = Σ(i=1..n) |x_i − z_i| / A · T_Dw_i · n_w
- `def f_energy_consumption` — F_ENERGY_CONSUMPTION:  Ec = (|C − A| · T / p) · Tcv
- `def f_height_node` — F_HEIGHT_NODE:  H = |g + A| − Tcv
- `def f_global_rzone` — F_GLOBAL_RZONE:  G = |r²| / ∂β · Tcv − β
- `def f_local_friction_d` — F_LOCAL_FRICTION_D:  fl = |δz − Tks| · (

---

## Semantic links

→ [[workers-cairrn-formulas]]
→ [[workers-cairrn-desktop]]
→ [[workers-cairrn-init]]
→ [[workers-cairrn-mycelial]]
→ [[workers-cairrn-constants]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-formulas-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-constants-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-desktop-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-worker-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-index-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
