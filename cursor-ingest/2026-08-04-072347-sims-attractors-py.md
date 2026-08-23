# sims / attractors.py

#source #python

> path: sims/attractors.py  
> ext: .py  

---

# sims / attractors.py


Bounded attractor simulations — Scribble-1 math.

Key facts encoded here
----------------------
d/dx(-e^x) = -e^x
  The negative exponential is closed under differentiation: its derivative
  is itself (sign preserved). This means no finite fixed point is stable
  under direct iteration of -e^x — the map diverges everywhere.

±1.96 as stable states
  1.96 is the 95 % Gaussian z-score: P(-1.96 < Z < 1.96) ≈ 0.95.
  It emerges as a *natural stability boundary* for normalised systems.

  To manufacture ±1.96 as attractors we use a symmetric double-well
  potential whose minima sit at ±α (α = 1.96

Defines: potential, potential_grad, potential_hess, stability_at, neg_exp, neg_exp_deriv, Trajectory, run_double_well, run_neg_exp_map, sweep_initial_conditions, summarise, record

---

## Semantic links

→ [[sims-attractors]]
→ [[attractors]]
→ [[attractors]]
→ [[sims]]
→ [[sims]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-sims-attractors-md]]
→ [[cursor-ingest/2026-08-04-072347-attractors-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-attractors-py]]
→ [[cursor-ingest/2026-08-04-072347-lambert-w-md]]
→ [[cursor-ingest/2026-08-04-072347-sims-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
