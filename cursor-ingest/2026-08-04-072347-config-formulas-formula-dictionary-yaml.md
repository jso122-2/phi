# config / formulas / formula_dictionary.yaml

#doc #yaml

> path: config/formulas/formula_dictionary.yaml  
> ext: .yaml  

---

# CAIRRN Formula Dictionary
# Source: desktop envelope photos + existing FORMULAS.md
# Canonised: 2026-07-21
#
# Each entry carries:
#   id          — unique formula identifier (matches code constant)
#   label       — human-readable name
#   expr        — canonical mathematical expression (LaTeX-style)
#   variables   — variable bindings (name → system field)
#   output      — what the formula produces
#   layer       — which CAIRRN layer uses it (1=modulation, 2=sharding, 3=coherence, X=composite)
#   source      — desktop image filename or existing module

# ────────────────────────────────────────────────────────────────────────────
# DESKTOP FORMULAS  (new, from envelope photos)
# ────────────────────────────────────────────────────────────────────────────

- id: F_CONSTRAINT_VAR
  label: Constraint Variable
  expr: "x_c = Lh / P - O"
  variables:
    Lh: likelihood          # float [0,1]
    P:  possibility         # float [0,1]
    O:  opportunity_cost    # float
  output: x_c               # constraint variable fed into F_FORECAST_SCORE
  layer: X
  source: "1765368575652.jpg"

- id: F_FORECAST_SCORE
  label: Forecast Score
  expr: "score = |(D - e) / x_c| * T * delta_j"
  variables:
    D:       forecasting_result   # float, percentage [0,1]
    e:       math_e               # constant 2.71828...
    x_c:     constraint_variable  # output of F_CONSTRAINT_VAR
    T:       temporal_validator   # float
    delta_j: energy_available     # float, Δj energy delta
  output: score
  layer: X
  source: "1765368575652.jpg"

- id: F_SCOPE_NAV
  label: Scope Navigation Score
  expr: "z = ||A + J| - beta| * x / sqrt(D)"
  variables:
    A:    current_node            # float, semantic position
    J:    current_objective       # float
    beta: energy_to_move          # float, energy required to reach desired node
    x:    boolean_temporal        # int {0, 1}
    D:    SHI                     # Semantic Hash Index (float > 0)
  output: z                       # scope co

---

## Semantic links

→ [[workers-cairrn-formulas]]
→ [[FORMULAS]]
→ [[workers-cairrn-mycelial]]
→ [[workers-cairrn-desktop]]
→ [[FORMULAS]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-formulas-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-formulas-md]]
→ [[cursor-ingest/2026-08-04-072347-formulas-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-formulas-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-desktop-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
