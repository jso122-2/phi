# workers / cairrn / formulas.py

#source #python

> path: workers/cairrn/formulas.py  
> ext: .py  

---

# workers / cairrn / formulas.py


CAIRRN routing formula functions — pure math, no state.

These are the **routing / desktop** formulas: they operate on the
Ana-Chi attractor pipeline (modulation → sharding → coherence).

⚠️  VARIABLE NAME DISAMBIGUATION
Variables like `energy`, `nutrients`, and `pressure` appear in both this
file and in `mycelial.py`, but they play different structural roles:

  formulas.py (routing layer)          mycelial.py (metabolic layer)
  ─────────────────────────────────    ──────────────────────────────
  energy     = CAIRRN routing energy   energy   = node metabolic energy
  nutrients  = SCUP nutr

Defines: f_constraint_var, f_forecast_score, f_cairrn_composite, f_energy_weighted, f_energy_consumption, f_height_node, f_global_rzone, f_local_friction_d, f_scope_nav, f_location_route, f_delta_two, f_tracer_consensus_k, f_tick_wisdom, f_cairrn_z_space

---

## Semantic links

→ [[workers-cairrn-formulas]]
→ [[workers-cairrn-init]]
→ [[workers-cairrn-mycelial]]
→ [[workers-cairrn-desktop]]
→ [[workers-cairrn-layers]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-formulas-md]]
→ [[cursor-ingest/2026-08-04-072347-workers-cairrn-mycelial-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-cairrn-formulas-py]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-workers-cairrn-desktop-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
