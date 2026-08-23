# source / sims-attractors.md

#doc #md

> path: source/sims-attractors.md  
> ext: .md  

---

# sims/attractors

#code #module #sims #math

> source_path: sims/attractors.py  
> package: sims  
> module: sims/attractors  
> hub: MATH  
> created_ts:   

---

**Package:** `sims`  
**Module:** `sims/attractors`  
**Source:** `sims/attractors.py`

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
  potential whose minima sit at ±α (α = 1.96):

      V(x)  = (x² - α²)²
      V'(x) = 4x(x² - α²)   ← gradient (force)

  Gradient-descent iteration:
      x_{n+1} = x_n - lr · V'(x_n)

  Fixed points of V' are x = 0 (unstable saddle) and x = ±α (stable).
  Stability check: V''(±α) = 4(3α² - α²) = 8α² > 0  ✓

Negative-exponential map (for reference)
  f(x)   = -e^x,   f'(x) = -e^x
  |f'(x)| = e^x > 1 for all x > 0  → no stable fixed point in ℝ⁺.
  The map is included here so you can watch it diverge and contrast with
  the double-well.

## API

- `def potential` — V(x) = (x² - α²)²  — minima at ±α.
- `def potential_grad` — V'(x) = 4x(x² - α²).
- `def potential_hess` — V''(x) = 4(3x² - α²).
- `def stability_at` — Return 'stable', 'unstable', or 'saddle' based on V''.
- `def neg_exp` — f(x) = -e^x.  Note: f'(x) = -e^x = f(x).
- `def neg_exp_deriv` — f'(x) = -e^x  (same as f — closed under differentiation).
- `class Trajectory`
- `def run_double_well` — Gradient descent on V(x) = (x² - α²)².
- `def run_neg_exp_map` — Iterate f(x) = -e^x.
- `def sweep_initial_conditions` — Run sim_fn for each starting point and return all trajectories.
- `def summarise` — Return a human-readab

---

## Semantic links

→ [[sims-attractors]]
→ [[sims]]
→ [[sims]]
→ [[sims-ana-chi]]
→ [[mcp-server-tools-sims]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-sims-md]]
→ [[cursor-ingest/2026-08-04-072347-sims-attractors-py]]
→ [[cursor-ingest/2026-08-04-072347-attractors-md]]
→ [[cursor-ingest/2026-08-04-072347-sims-init-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-attractors-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
