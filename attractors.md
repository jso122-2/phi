# attractors

#math #code #hub

Stable-state mathematics and gradient-descent implementation.

---

## Connections

→ [[MATH]] ← math hub  
→ [[HOME]] ← grand central  
→ [[harmonic-index]] — trajectories inject into harmonic shards  
→ [[sims]] — implemented in `sims/attractors.py`  
→ [[lambert-w]] — the other attractor in this system  
→ [[mcp-server]] — exposed as `double_well_sim`, `neg_exp_sim`, `sweep_attractors`  

---

## Double-well potential

```
V(x) = (x² − α²)²        α = 1.96

V′(x) = 4x(x² − α²)      gradient (force)
V″(x) = 4(3x² − α²)      Hessian (curvature)
```

### Fixed points

| x | V′(x) | V″(x) | Type |
|---|---|---|---|
| 0 | 0 | −4α² < 0 | **Unstable saddle** |
| +α | 0 | +8α² > 0 | **Stable well** |
| −α | 0 | +8α² > 0 | **Stable well** |

### Gradient descent iteration

```
x_{n+1} = x_n − lr · V′(x_n)
         = x_n − lr · 4x_n(x_n² − α²)
```

Converges to +α if x₀ > 0, −α if x₀ < 0.  
Step is capped at `max_step = 0.5` to prevent oscillation at large |x₀|.

---

## Negative-exponential map

```
f(x)  = −eˣ
f′(x) = −eˣ       (closed under differentiation)
```

Despite this, f converges to x* ≈ −0.5671 because |f′(x*)| = W(1) ≈ 0.567 < 1.  
See [[lambert-w]] for the full derivation.

---

## Python API

```python
from sims.attractors import (
    ALPHA,              # 1.96
    potential,          # V(x)
    potential_grad,     # V′(x)
    potential_hess,     # V″(x)
    stability_at,       # 'stable' | 'unstable' | 'not a fixed point'
    run_double_well,    # gradient descent → Trajectory
    run_neg_exp_map,    # iterate f(x)=−eˣ → Trajectory
    sweep_initial_conditions,
    summarise,
)
```

### `Trajectory` dataclass

| Field | Type | Meaning |
|---|---|---|
| `x0` | float | Starting position |
| `steps` | list[float] | All positions recorded |
| `converged` | bool | Whether tolerance was met |
| `converged_at` | float\|None | Final convergence value |

---

## Run it now

```
/sim 1.5          → double_well_sim(x0=1.5)
/sim -2.0         → converges to −1.96
/neg-exp 0.0      → neg_exp_sim(x0=0.0)
/sweep            → sweep_attractors() over [−4, +4]
```

---

## Auto-linked

→ [[COMMANDS]]
→ [[CODE]]
→ [[workers]]
→ [[live-state]]
→ [[2026-07-13-120800-dawn-physics-scaffold-and-mycelial-layer-context-dump]]
→ [[psspps]]

→ [[cairrn]]
→ [[temporal-index]]
→ [[2026-07-13-integrate-ana-chi-constant-modulate-cairrn-stable-states]]
→ [[ana-chi]]
→ [[sessions]]

→ [[hub-classifier]]
→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[README]]
→ [[graph]]

→ [[logger]]
→ [[git-log]]
→ [[worker]]
→ [[2026-07-16-011935-mcp-tool-command-reference]]
→ [[2026-07-13-095004-cairrnify-the-mcp-server-fix-dom-queue-open]]

→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-16-011935-cairrn-cairrn-worker-system]]
→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]
→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]
→ [[2026-07-16-011935-slash-commands-spotify-rip]]
→ [[2026-07-16-011935-spotify-rip-slash-commands]]

→ [[config]]
→ [[cursor-skills]]
→ [[2026-07-16-011935-mamba-environment-spotify-rip]]
→ [[dev]]
→ [[2026-07-16-011935-scribble-files-are-read-only]]
→ [[2026-07-16-011935-find]]
