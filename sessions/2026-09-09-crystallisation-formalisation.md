# Session: 2026-09-09 — f_crystallisation formalisation

#session #formalisation #autonomous-index #formulas

---

## What this session documents

Integration mapping for `f_crystallisation` from `workers/cairrn/formulas.py` into the
autonomous-index Si_delta rewrite threshold. Phase A of the `/talk`-agreed plan to wire
10 decorative math functions in `workers/cairrn/formulas.py` into live protocol use.

---

## The formula

**Source:** `workers/cairrn/formulas.py` lines 788–809

```python
def f_crystallisation(eta: float, t_min: float, shimmerfield_t0: float) -> float:
    """C_thresh = η^t_min · shimmerfield_t0"""
    eta_safe = max(min(float(eta), 1.0 - 1e-9), 1e-9)
    return (eta_safe ** t_min) * abs(shimmerfield_t0)
```

**Math:** `C_thresh = η^t_min · shimmerfield_t0`

Original semantics: power-law settling threshold for the Spotify prefeed route —
the shimmer field must decay below `C_thresh` before the route is considered stable
and a prefeed commit is allowed.

---

## Layer mapping

| autonomous-index concept | f_crystallisation parameter | Mapping |
|---|---|---|
| `Si_delta = R_node − R_node_prev` | — | The velocity signal being thresholded |
| R_node at start of observation window | `shimmerfield_t0` | "amplitude at start of cool phase" = initial R_node value, captured as R_node_prev on first tick of observation |
| Per-tick decay factor | `eta` | How fast the threshold tightens as ticks accumulate. Default: **0.9** |
| Observation window length (ticks) | `t_min` | Minimum ticks before a Si absolute rank rewrite is allowed. Default: **3** |
| **C_thresh** | return value | Minimum `|Si_delta|` required to trigger Si absolute rank rewrite |

**Rewrite trigger:**
```
|Si_delta| > C_thresh
    where C_thresh = f_crystallisation(η=0.9, t_min=3, shimmerfield_t0=R_node_prev)
```

**Physical interpretation:**
- Large R_node_prev (cold shard, high radial position) → large C_thresh → threshold is high → only a large velocity delta triggers a rewrite. Stable cold shards are protected from thrashing.
- Small R_node_prev (hot shard, low radial position) → small C_thresh → even a small velocity delta triggers a rewrite. Hot shards track change quickly.
- η = 0.9, t_min = 3 → C_thresh = 0.9³ · R_node_prev = 0.729 · R_node_prev. After 3 ticks, ~73% of the initial amplitude is the threshold. Reasonable sensitivity.

---

## Variable mapping: shimmerfield_t0 → R_node

In the Spotify pipeline, `shimmerfield_t0` is the shimmer amplitude at start of the cool phase.
In the autonomous-index context, it maps to `R_node_prev` — the R_node value written by Claude
at the start of the current observation window (equivalently, before the current tick fires).

This is not approximate. R_node is the reservoir's radial position score:
```
R_node = 1 / (Ta·0.5 + C_relevance·0.3 + Qe·0.2)
```
A newly cold shard has high R_node (large denominator not yet built up). A hot shard has low R_node.
This is structurally identical to shimmerfield_t0 as a "starting amplitude" — large for cold, small
for hot. The mapping is exact.

---

## Decision log

**Decision 1 (portability):** `f_crystallisation` is called from both pipelines via the shared
implementation in `workers/cairrn/formulas.py`. Not duplicated.

**Decision 2 (formalise first):** This note exists before any code is wired.
The SKILL.md update in `reservoir/skills/autonomous-index/SKILL.md` is Step 5;
Python wire is Phase B (flagged below).

**Decision 3 (start here):** `f_crystallisation` was chosen first because Si_delta's threshold
is explicitly undefined in the autonomous-index protocol. Zero ambiguity about what it replaces.

---

## Phase B flag — Python wire is deferred

Si_delta is **not in Python code yet**. It is a Notion formula field on Shard rows
(`Si_delta = R_node − R_node_prev`) and a protocol rule in autonomous-index SKILL.md.

The Phase A wire (this session) updates the .md spec only.
Phase B (Python wire) is deferred to a future `/dev` session and should:

1. Add `si_delta` as a field to the shard score dataclass (wherever Shard scores are tracked in Python)
2. Import `f_crystallisation` from `workers.cairrn.formulas` at the Si rewrite call site
3. Apply the threshold check: `if abs(si_delta) > f_crystallisation(0.9, 3, r_node_prev): rewrite_si_rank()`

Candidate Python locations (currently no Si_delta in Python):
- `phi/models/psp_index.py` — has `Si_delta` references (check what they are)
- Any future shard score tick handler

---

## Cross-layer resonance

`f_crystallisation` as C_thresh joins three other power-law / exponential suppression
patterns already present in the stack:
- Layer 0: Shimmer Decay `S(t) = S₀e^{-λt}`
- Layer 5: Ns2 penalty `e^(Ss)`
- Layer 6: Entry Decay `D(t) = Cw · e^{-λ·Δt}`

`f_crystallisation` uses `η^t_min` (discrete power-law) rather than continuous exponential,
but the mathematical role is identical: suppress/threshold based on accumulated time
times an initial amplitude. Fourth instance of the same structural move.

---

## Graph links

→ [[autonomous-index]] — SKILL updated this session
→ [[formulas]] — source of f_crystallisation
→ [[10-notion-data-stream-score-formalisation]] — Si_delta defined in Layer 7
→ [[12-shards-database-formulas]] — Si_delta formula and field definitions
→ [[sessions]] — session index

*Phase A complete. Phase B deferred. SKILL.md updated.*
