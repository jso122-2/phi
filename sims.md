# sims

#code #math #hub

The simulation engine — pure Python, numpy-backed.

---

## Connections

→ [[CODE]] ← code hub  
→ [[HOME]] ← grand central  
→ [[attractors]] — mathematical basis for `sims/attractors.py`  
→ [[harmonic-index]] — mathematical basis for `sims/harmonic.py`  
→ [[workers]] — workers wrap sim functions  
→ [[mcp-server]] — sims exposed as MCP tools  

---

## `sims/attractors.py`

| Export | Type | Purpose |
|---|---|---|
| `ALPHA` | float | 1.96 — attractor location |
| `potential(x, alpha)` | fn | V(x) = (x²−α²)² |
| `potential_grad(x, alpha)` | fn | V′(x) = 4x(x²−α²) |
| `potential_hess(x, alpha)` | fn | V″(x) = 4(3x²−α²) |
| `stability_at(x, alpha)` | fn | 'stable' \| 'unstable' \| 'not a fixed point' |
| `neg_exp(x)` | fn | f(x) = −eˣ |
| `neg_exp_deriv(x)` | fn | f′(x) = −eˣ (same) |
| `NEG_EXP_FIXED_POINT` | float | −0.5671432904097838 |
| `run_double_well(x0, ...)` | fn | gradient descent → Trajectory |
| `run_neg_exp_map(x0, ...)` | fn | iterate f(x)=−eˣ → Trajectory |
| `sweep_initial_conditions(x0s, fn)` | fn | run fn for each x0 |
| `summarise(traj, alpha)` | fn | human-readable summary dict |
| `Trajectory` | dataclass | x0, steps, converged, converged_at |

---

## `sims/harmonic.py`

| Export | Type | Purpose |
|---|---|---|
| `HarmonicShard` | dataclass | index, harmonic, activation, basin_centre |
| `LocalPropagator` | class | discrete wave update on shard ring |
| `HarmonicIndex` | class | full sharded index with inject/propagate/state/reset |

### `HarmonicIndex` methods

| Method | Signature | Effect |
|---|---|---|
| `inject` | `(shard_index, value=1.0)` | Direct activation injection |
| `inject_from_trajectory_final` | `(final_x, value=1.0)` | Map to nearest basin, inject |
| `propagate` | `(steps=1)` | Run wave update N times |
| `total_activation` | `()` | Sum of all shard activations |
| `peak_shard` | `()` | Shard with highest activation |
| `state` | `()` | Serialisable snapshot dict |
| `reset` | `()` | Zero activations + step counter |

---

## Tests

```
tests/test_attractors.py
tests/test_harmonic.py
```

Run with `/test` or:

```bash
mamba run -n spotify-rip pytest tests/test_attractors.py tests/test_harmonic.py -v
```

---

## Auto-linked

→ [[live-state]]
→ [[MATH]]
→ [[COMMANDS]]
→ [[psspps]]
→ [[lambert-w]]

→ [[cairrn]]
→ [[temporal-index]]
→ [[ana-chi]]
→ [[2026-07-13-integrate-ana-chi-constant-modulate-cairrn-stable-states]]

→ [[hub-classifier]]
→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]
→ [[sessions]]
→ [[README]]
→ [[graph]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]

→ [[2026-07-16-011935-cairrn-cairrn-worker-system]]
→ [[logger]]
→ [[2026-07-16-011935-mcp-tool-command-reference]]
→ [[git-log]]

→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]
→ [[2026-07-13-095004-cairrnify-the-mcp-server-fix-dom-queue-open]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-16-011935-slash-commands-spotify-rip]]
→ [[2026-07-16-011935-spotify-rip-slash-commands]]
→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]

→ [[cursor-skills]]
→ [[config]]
→ [[2026-07-16-011935-mamba-environment-spotify-rip]]
→ [[dev]]
→ [[2026-07-16-011935-scribble-files-are-read-only]]
→ [[2026-07-16-011935-find]]
