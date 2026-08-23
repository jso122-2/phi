# mfpt — Mean First Passage Time

#math #code

The mean first passage time (MFPT) for thermally-activated escape from a
double-well attractor. Bridges the integral from the MFPT derivation to the
Langevin dynamics implementation and the Kramers analytical prediction.

---

## Connections

→ [[MATH]] ← math hub  
→ [[attractors]] — the double-well V(x) this escape operates on  
→ [[harmonic-index]] — Langevin final positions inject into harmonic shards  
→ [[sims]] — implemented in `sims/attractors.py`  
→ [[mcp-server]] — exposed as `langevin_sim`, `mfpt_estimate`  
→ [[lambert-w]] — fixed point of −eˣ; convergence via |f′(x*)| < 1  

---

## The MFPT integral

For any exponentially distributed escape process with rate λ:

\[
\tau = \frac{\int_0^\infty \lambda N_0 t\, e^{-\lambda t}\, dt}{N_0}
     = \lambda \int_0^\infty t\, e^{-\lambda t}\, dt
\]

Integration by parts with u = t, dv = e^{−λt} dt:

\[
\tau = \lambda \left[\frac{t\, e^{-\lambda t}}{-\lambda}\right]_0^\infty
      - \lambda \int_0^\infty \frac{e^{-\lambda t}}{-\lambda}\, dt
    = 0 + \int_0^\infty e^{-\lambda t}\, dt = \frac{1}{\lambda}
\]

**τ = 1/λ** — mean dwell time in a well is the reciprocal of the escape rate.

---

## Kramers rate for V(x) = (x² − α²)²

The overdamped Kramers formula (γ = 1 convention):

\[
\lambda = \frac{\omega_0 \cdot \omega_s}{2\pi} \exp\!\left(-\frac{\Delta V}{D}\right)
\]

Quantities for this system (α = 1.96):

| Symbol | Formula | Value |
|---|---|---|
| ΔV | V(0) − V(±α) = α⁴ | **14.7579** |
| ω₀ | √V″(±α) = 2√2·α | **5.5436** |
| ωₛ | √\|V″(0)\| = 2α | **3.92** |
| D | noise_scale² | user-controlled |
| λ | Kramers rate (s⁻¹ in continuous time) | D-dependent |
| τ | 1/λ (continuous) | D-dependent |
| τ_steps | τ / lr (discrete steps) | D and lr dependent |

### Practical noise_scale guide

| noise_scale | D = σ² | ΔV/D | Regime | τ_steps (lr=0.05) |
|---|---|---|---|---|
| 1.0 | 1.0 | 14.76 | Deep barrier — very rare escape | ≈ 10⁸ |
| 1.5 | 2.25 | 6.56 | Moderate — censoring likely | ≈ 10⁴ |
| 2.0 | 4.0 | 3.69 | Measurable — 200 trials viable | **≈ 231** |
| 3.0 | 9.0 | 1.64 | Fast — Kramers approx. breaks down | ≈ 3 |
| 3.84 | ~14.76 | 1.0 | ΔV = D — fully activated | ≈ 1 |

At ΔV/D ≈ 3.7 (noise_scale=2.0), empirical MFPT ≈ 0.5 × Kramers prediction.
The Kramers formula overshoots because the pre-exponential factor dominates
when the barrier is not deep relative to noise — this is expected.

---

## Langevin dynamics

The discrete overdamped Langevin update rule:

```
x_{n+1} = x_n − lr · V′(x_n) + √(2·D·lr) · ξ       ξ ~ N(0,1)
```

- At noise_scale = 0: reduces to deterministic gradient descent (`run_double_well`)
- At noise_scale > 0: thermally-activated escape possible
- Both ±α → same harmonic shard (index 0, basin centre 1.96)

---

## Python API

```python
from sims.attractors import run_langevin, kramers_rate, measure_mfpt, ALPHA

# Single stochastic trajectory
traj = run_langevin(x0=ALPHA, noise_scale=2.0, max_iter=500, seed=42)

# Analytical Kramers prediction
k = kramers_rate(noise_scale=2.0)
# k["tau_steps"]    → 231.4  (predicted MFPT in discrete steps)
# k["rate"]         → 0.0864 (escape rate per time unit)
# k["delta_V"]      → 14.76  (barrier height = α⁴)

# Empirical MFPT — 200 independent escape trials
result = measure_mfpt(noise_scale=2.0, n_trials=200, seed=0)
# result["mean_escape_steps"]       → measured τ
# result["kramers_tau_steps"]       → predicted τ
# result["ratio_empirical_kramers"] → empirical / prediction (≈ 0.5 at ΔV/D=3.7)
```

---

## MCP tools

```
/langevin <x0>            → langevin_sim(x0, noise_scale=2.0, steps=500)
/mfpt [noise_scale]       → mfpt_estimate(noise_scale, n_trials=200)
```

---

## Shard lifetime analogue

The isometric propagation mode decays shard activation by κ per step.
Treating each propagation step as dt, the mean shard lifetime is:

```
a(t) ≈ a₀ · e^{−κt}   →   τ_shard = 1/κ = 1/0.15 ≈ 6.67 steps
```

This is the **same integral** applied to the harmonic ring — the MFPT formula
τ = 1/λ connects both the physical attractor escape time and the
harmonic decay timescale.

Reference: Kramers (1940), Physica 7, 284.

---

## Auto-linked

→ [[attractors]]
→ [[harmonic-index]]
→ [[MATH]]
→ [[COMMANDS]]
→ [[mcp-server]]
→ [[sims]]
