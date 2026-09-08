# 📐 Phi Codebase — Score Formalisation

*Source: local `phi/` on disk (not in the 2026-09-07 Notion export)*
*Captured: 2026-09-08*

The Notion canonical stack (Layers 0–9) never ingested the player/library graph.
Those formulas already run in Python. This page is the law for that surface.

**Find result.** Notion MCP was not connected. Search was the Reservoir export
(`reservoir/maths/01`–`12`) plus on-disk `phi/`. Matches in Notion: none for
D4, T_B, buoyancy, helm, arc continuation, or E_coh. TP-RAR exists in
`config/formulas/formula_dictionary.yaml` and `workers/cairrn/formulas.py`
but is **not** restated in the Notion stack.

**Read result — unused by Notion, live in phi.** Session-fit ranker, helm floor,
novelty half-life, ash-yield ELO K, TP-RAR keep/fill, adaptive capacity / Cc,
dragon D4_A/D4_B, arc continuation, song-derivative D1–D4, Euler–Poincaré +
basin sequestration, coherence energy, T_B → retrieval α, exponentiated-gradient
weight learning.

---

## Unified variable key

| Symbol | Meaning | Code |
|---|---|---|
| C_E | Session-fit confidence (ranker `score`) | `phi.core.ranker.TrackRanker.score` |
| B | Buoyancy ∈ [0, 1] | `phi.meta.consensus.buoyancy_score` |
| w° | Base helm/novelty/elo mix (simplex) | `WEIGHTS` |
| w | Buoyancy-scaled, renormalised mix | `_confidence_weights` |
| N | Novelty ∈ [0, 1] | `_novelty_score` |
| t½ | Novelty half-life (days) | `NOVELTY_HALF_LIFE = 14` |
| A_yield | Ash-boosted ELO K | `ash_yield` |
| cl_E | Key/BPM/completion confidence | `_confidence_level` |
| Δt | Play-age in half-lives + abandon | `_time_delta` |
| p | Skip pressure = skips / plays | `_skip_pressure` |
| λ | ln 2 / t½ | `TP_RAR_LAMBDA` |
| AC | Adaptive capacity | `adaptive_capacity` |
| Cc | Spendable energy budget | `cc_budget_score` |
| D4_A | Dragon norm-ratio | `DragonCurve.score_a` |
| D4_B | Dragon fold projection | `DragonCurve.score_b` |
| S_arc | Arc continuation | `ArcScorer.score_candidate` |
| χ | Euler characteristic | `TopologicalInvariant.chi` |
| T_B | Basin sequestration | `basin_sequestration` |
| α_ret | Retrieval locality | `t_b_to_alpha` |
| E_coh | GNN coherence energy | `phi.gnn.coherence` |

---

## Pipeline (next-track)

```
C_E  →  TP_RAR keep/fill  →  Cc keep/fill  →  top-N
```

1. `score` produces C_E (predicted_completion if present, else helm mix).
2. `tp_rar_score(C_E, cl_E, Δt, p)` ranks the same pool.
3. `keep_fill` keeps scores ≥ mean, then fills with the rest (`F_SECONDARY_MODEL_SELECT`).
4. `cc_budget_score(AC, p, Tcv)` reorders by spendable budget.
5. Same keep/fill, take N.

Adjacent structure (mood graph, genre tags) never increments Qe. Same Law 6 as Notion: annotation is routing, access is scoring.

---

## F_SESSION_FIT — C_E

```
C_E = predicted_completion                         if annotated
C_E = Σ_k w_k · x_k                                otherwise
```

| k | x_k | w° |
|---|---|---|
| genre | CLAP cosine / Jaccard / substring | 0.28 |
| mood | CLAP cosine / valence-energy L2 / label+adjacency | 0.28 |
| novelty | N | 0.23 |
| elo | clamp((ELO − 1200) / 600, 0, 1) | 0.13 |
| phi_rank | RankArm annotation or 0.5 | 0.08 |

Mood Euclidean fallback:

```
x_mood = 1 − √((Δv)² + (Δe)²) / √2
```

---

## F_BUOYANCY — catalog authority

```
coverage  = n_catalog / 4          catalog ∈ {spotify, mb, lastfm, discogs}
agreement = mean(BPM conf, mood confirm, genre-consensus cardinality)
B         = clamp((coverage + agreement) / 2, 0, 1)
```

B = 0 when coverage = 0. High B → helm owns heading. Low B → dampen helm; do **not** hand authority to ELO/novelty.

---

## F_HELM_WEIGHTS — skip-spiral guard

```
helm_scale = max(0.50, B)
w_genre    = w°_genre    · helm_scale
w_mood     = w°_mood     · helm_scale
w_phi      = w°_phi_rank · helm_scale
w_novelty  = w°_novelty                  (flat)
w_elo      = w°_elo                      (flat)
w          = w / Σ w
```

HELM_FLOOR = 0.50. Helm dims never fall below half their prior share, so sparse enrichment cannot renormalise ELO/novelty into the helm.

---

## F_NOVELTY — half-life freshness

```
N = 0.85                                          never played
N = min(1, 1 − exp(−days · ln 2 / t½))            otherwise
```

t½ = 14 days. Same exponential family as shimmer decay (Layer 0) and Ns2 (Layer 8). Unused time *raises* N (library freshness), unlike shimmer which *lowers* intensity. Dual of Law 1: exponential in time, inverted intent.

---

## F_ASH_YIELD — coherent-session ELO K

Phi wrap (capped):

```
T_excess = max(0, consecutive_coherent_plays − 3)
A_yield  = min(32, 8 · exp(0.20 · T_excess))
```

CAIRRN primitive (uncapped):

```
A_yield = A_base · exp(k · (T − T_min))
```

Phi: A_base = 8, k = 0.20, T_min = 3, cap = ELO_K = 32.

---

## F_TP_RAR — time-penalised risk-adjusted return

Already in the YAML dictionary. Restated here because the Notion stack omitted it.

```
λ      = ln 2 / t½
cl_E   = mean(key_confidence, bpm_confidence, completion_rate)   else 0.5
Δt     = days/t½ + (1 − completion_rate)
p      = clamp(skips / plays, 0, 1)                              else 0
TP_RAR = (C_E − (1 − cl_E)·λ − Δt·p) / max(|conf_ma|, ε)
```

`MS_i = 1` iff TP_RAR_i < mean (fill, not keep).

---

## F_ADAPTIVE_CAPACITY and F_CC

```
AC = (1/3)·N_headroom + (1/3)·M_SHI + (1/3)·S_T + A
A_used = max(0, E_max − min(E_max, AC))
Cc     = ((c − A_used) / p) · Tcv
```

Phi maps high AC → lower A_used → higher Cc (`cc_budget_score`). Pressure p is skip pressure. Guard p ≠ 0 at 1e-9 in `f_cc_energy_budget`.

---

## F_D4_A / F_D4_B — dragon fold scores

Fold sequence:

```
seq(1) = [1]
seq(k) = seq(k−1) ⌢ [1] ⌢ reverse_complement(seq(k−1))
```

depth k → 2^k segments. Bit 1 = right turn, 0 = left.

At nearest segment i with points p0, p1, p2:

```
D1   = p1 − p0
D2   = (p1_y + p2_y) / 2
D3   = p2
d_⊥  = (−D1_y, D1_x) / ‖D1‖

D4_A = ‖D3‖ / ‖D1‖ − D2
D4_B = |D3 · d_⊥| / ‖D1‖ − D2 · (d_⊥)_y
```

D4_A is rotation-invariant (regression target). D4_B is fold-direction (XGBoost feature). Zero if ‖D1‖ < 1e-9.

---

## F_ARC_CONTINUATION — next D4_A on the session curve

Buffer of last 16 played D4_A values. Neutral level = 10 (mid of [1, 20]).

```
level  = mean(buffer)
slope  = linregress(last 8)_slope          (0 if n < 3)
target = level + slope
S_arc  = 1 / (1 + |d4_a − target| · 0.1)
```

S_arc = 1 perfect continuation; ≈ 0.5 at Δ = 10; → 0 on a jarring jump.

---

## F_SONG_DERIVATIVE — hierarchical library curve

```
D1 = XGB(acoustic ∪ tonal)
D2 = XGB(social ∪ D1)
D3 = (D1 + D2) / 2
D4 = rolling_mean(D3, window = 0.15 · |library|)
```

Distinct from dragon D4_A. Do not collapse the two D4 families. Dragon D4 is geometric fold; song D4 is a smoothed master score across the sorted library.

---

## F_EULER_CHI — graph homology snapshot

```
χ  = V − E + T
β₁ = max(0, β₀ − χ)                         (component proxy)
β₀ = V − rank(∂₁)                           (matrix rank, optional)
β₁ = rank(∂₁) − rank(∂₂)

∂₁ ∘ ∂₂ = 0
```

Fast GNN fallback uses χ ≈ V − E (T omitted). Full primitive includes triangles.

---

## F_BASIN_SEQUESTRATION — T_B

```
D    = V / max(β₀, 1)                       diameter proxy
D_M  = E / max(V, 1)                        mean degree
A_xG = V · D · √max(D_M, 0)
BSH  = β₁ − D
Sc   = χ · β₀
BHD  = Sc − D

T_B      = A_xG · |BSH| / max(T, 1) − |BHD − 1|
t_b_norm = tanh(T_B / max(V², 1))
α_ret    = 0.5 + 0.5 · clamp(t_b_norm, −1, 1)
```

T_B > 0 → deep basin, sequestered activation, α_ret → 1 (local retrieval).
T_B < 0 → open basin, α_ret → 0 (global retrieval).

D is a component-size proxy, not graph diameter. Flagged in code for `nx.diameter()` when V < 1000.

---

## F_COH_ENERGY — GNN negative-energy regulariser

```
E_coh = −α·J(h) + β·hᵀLh + γ·Φ(dA) + δ·Ω(h_layers) + ε·χ(G)
```

| Term | Role | Default weight |
|---|---|---|
| J(h) ≈ |kurtosis| | Negentropy — reward non-Gaussian structure | α = 0.10 |
| hᵀ L h | Laplacian smoothness on edges | β = 0.05 |
| Φ = mean ReLU(σ(A_log) − 0.99) | Lyapunov: keep SSM contractive | γ = 0.08 |
| Ω = mean KL(softmax h_ℓ ‖ softmax h_{ℓ+1}) | Layer drift | δ = 0.03 |
| χ loss = 1 − exp(−|χ − χ*| / scale) | Topology vs target | ε = 0.04 |

χ_scale = max(|χ|, |χ*|, V, 1). χ* default = 1 (tree-like community).

Weight schedule: 0 until warmup 0.15; cosine ramp to ramp 0.40; then full.

---

## F_EG_WEIGHTS — exponentiated-gradient simplex

```
w_k ← w_k · exp(η · y · x_k)
w   ← simplex(max(w_k, 0.05))
```

η = 0.08. y = +1 if completion ≥ 0.70, y = −1 if completion < 0.30, else no update.

---

## Routing logic

| Condition | Classification |
|---|---|
| High B, helm dims dominate C_E | Catalog-confident heading |
| Low B, helm floored | Sparse enrichment — ELO/novelty must not take the wheel |
| High N, never played | Freshness push (0.85), not maximum |
| High p, large Δt | TP-RAR suppresses even high C_E |
| High AC | Cc budget opens; more tracks spendable |
| S_arc low | Arc jump — do not treat as genre mismatch |
| T_B > 0 | Local retrieval (α_ret high) |
| Deeply negative T_B | Open basin — widen search, same spirit as high PSI |

---

## Open flags

**Two D4 families.** Dragon D4_A/B vs song-derivative D1–D4 share a letter and must stay namespaced (`F_D4_A` vs `F_SONG_DERIVATIVE`).

**Ash-yield cap.** Phi caps at 32; CAIRRN `f_ash_yield` does not. Documented as two realisations of one Arrhenius form.

**T_B diameter proxy.** D = V/β₀, not geodesic diameter.

**χ gradient.** Euler-characteristic loss is a monitor on fixed edge sets (gradient zero w.r.t. embeddings). Laplacian term carries topology gradient.

**Ns2 vs novelty N.** Notion Ns2 *penalises* unused deep shards. Phi N *rewards* unused tracks. Same exponential, opposite retrieval policy. Do not substitute.

---

## Python reference

```python
import math

def novelty(days: float | None, half_life: float = 14.0, never: float = 0.85) -> float:
    if days is None:
        return never
    return min(1.0, 1.0 - math.exp(-days * math.log(2) / half_life))

def ash_yield_phi(coherent_plays: int, a_base=8.0, k=0.20, t_min=3, cap=32.0) -> float:
    t = max(0, coherent_plays - t_min)
    return min(cap, a_base * math.exp(k * t))

def helm_weights(buoyancy: float, base: dict[str, float], floor: float = 0.50) -> dict[str, float]:
    scale = max(floor, buoyancy)
    w = {
        "genre": base["genre"] * scale,
        "mood": base["mood"] * scale,
        "phi_rank": base["phi_rank"] * scale,
        "novelty": base["novelty"],
        "elo": base["elo"],
    }
    s = sum(w.values())
    return {k: v / s for k, v in w.items()}

def d4_a(d1, d2: float, d3) -> float:
    n1 = float((d1[0] ** 2 + d1[1] ** 2) ** 0.5)
    if n1 < 1e-9:
        return 0.0
    n3 = float((d3[0] ** 2 + d3[1] ** 2) ** 0.5)
    return n3 / n1 - d2

def arc_score(d4_a: float, level: float, slope: float, scale: float = 0.1) -> float:
    return 1.0 / (1.0 + abs(d4_a - (level + slope)) * scale)

def t_b_to_alpha(t_b_norm: float) -> float:
    return 0.5 + 0.5 * max(-1.0, min(1.0, t_b_norm))

def euler_chi(V: int, E: int, T: int = 0) -> int:
    return V - E + T
```

---

## Source modules (do not edit this list into law — the formulas above are law)

- `phi/core/ranker/_scoring.py` `_track.py` `_tp_rar.py` `_capacity.py` `_learn.py` `_constants.py`
- `phi/meta/consensus.py`
- `phi/models/dragon_curve.py` `d4_model.py` `song_derivative.py`
- `phi/engine/arc_scorer.py`
- `phi/topology/primitives.py`
- `phi/gnn/coherence.py`
- `phi/engine/vault_context.py` `graph/topology_index.py`
- `workers/cairrn/formulas.py` `workers/cairrn/mycelial.py`
