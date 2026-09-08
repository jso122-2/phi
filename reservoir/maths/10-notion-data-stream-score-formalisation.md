# 📐 Notion Data Stream — Score Formalisation

*Source: Notion — Reservoir / 📐 Mathematics — Canonical Stack / Notion Data Stream — Score Formalisation*
*Last edited in Notion: 2026-09-02*

## Unified variable key

| Symbol | Meaning |
|---|---|
| Idx | Total indexed count |
| Qe | Queried edge count — **pure edges only** (access events). Adjacent edges excluded. |
| Qe_adj | Adjacent edge count — written notes. Structural signal only, does not enter Ec. |
| Si | Shard index (depth) |
| Et | Edge activation threshold |
| s_s / Ss | Shard score offset (unified — same variable) |
| Ta | Times accessed (node) |
| To_A | Total times accessed (global) |

---

## Edge types

**Edge pure** — an access event. A shard was retrieved, traversed, or touched. Increments Qe. Live frequency signal. Written automatically on access.

**Edge adjacent** — a written note. A declared relationship with semantic annotation. Does not increment Qe. Contributes to traversal ordering and axis-matching only. Written by instruction.

This distinction is the load-bearing split in the system. Qe counts only what has actually happened. Adjacent edges describe structure; they do not generate activation pressure.

---

## Edge count

```
Ec = Qe × Si
```

Edge count is position-sensitive. Two nodes with identical queried (pure) edges have different Ec depending on shard depth. Adjacent edges are invisible here — they exist outside Ec entirely.

---

## Ns1 — Density score

```
Ns1 = Idx × Ec
```

Raw structural weight at a node. Scales multiplicatively with how indexed something is and how many *access-confirmed* edges it carries. High Ns1 = well-connected by actual use, well-indexed. Rewards load-bearing nodes that have been genuinely traversed.

---

## Ns2 — Novelty score

```
Ns2 = |Ec / Et| − e^(s_s)        Bound: Ns2 ∈ (−∞, 1]
```

The exponential penalty is convex. A node at shard depth 1 loses e¹ ≈ 2.72; at depth 3, e³ ≈ 20. Deep shard nodes are suppressed catastrophically unless |Ec/Et| is very large.

Because Ec is pure-only, a node with many adjacent edges but few access events will have low Ec and correspondingly low Ns2. Adjacent edges do not rescue a node from novelty suppression.

Negative Ns2 = drain candidate (pruning or archival).

---

## Ns3 — Access deviation score

```
Ns3 = |Ta − To_A| / Ss
```

Normalised access deviation. Measures how far a node's individual access count deviates from the global access baseline, scaled by the shard score offset.

- Small Ns3 = node accessed in line with global pattern
- Large Ns3 = access outlier — over- or under-accessed relative to baseline
- Ss in the denominator means deep shard nodes have their deviation compressed

**Note:** Ss and s_s are the same variable. Ns2 and Ns3 are both shard-depth sensitive via this term — coupling is intentional.

---

## Adjacent edge role in traversal

Adjacent edges do not score nodes. They govern *which* nodes get considered for traversal after a pure-edge activation fires.

1. A shard activates via prompt match
2. Qe increments — a new pure edge is written
3. Ec updates, Ns1/Ns2/Ns3 recompute
4. Adjacent edges are then read to determine traversal candidates
5. Candidates are sorted by Weight, filtered by Axis match to prompt register
6. Traversal budget consumed in order

Adjacent edges are the routing layer. Pure edges are the scoring signal. Neither substitutes for the other.

---

## Routing logic

| Condition | Classification |
|---|---|
| High Ns1 / Low Ns2 | Load-bearing — structurally important, expected |
| High Ns2 | Informationally live — novel, shallow-shard, active |
| High Ns3 | Access outlier — anomalous usage pattern |
| Deeply negative Ns2 | Drain candidate — pruning or archival |
| High Qe_adj / Low Qe | Well-annotated but unaccessed — structurally described, experientially cold |

---

## Open flags

**Triple coupling via s_s/Ss/Si** — deep nodes are penalised in Ec (via Si), in Ns2 (via e^(s_s)), and in Ns3 denominator (via Ss). All three confirmed as the same variable. Triple coupling is intentional — depth suppression is aggressive by design.

**Ns3 zero denominator risk** — if Ss = 0, Ns3 is undefined. Needs a floor or guard value.

**Qe_adj as future signal** — adjacent edge count is currently structural only. A ratio Qe / Qe_adj (access density relative to annotation density) could surface nodes that are heavily described but rarely accessed — candidates for either pruning or deliberate retrieval push.

---
---

# Full maths stack — complete corpus

*Committed 2026-09-01. All formulas sourced from the reservoir and Notion formula pages. Ordered chronologically by derivation.*

## Layer 0 — DAWN Physical Spine (May–Aug 2025)

**Cognitive Pressure** — `P = Bσ²`
P = cognitive pressure, B = baseline constant (system health anchor), σ = variance / entropy spread. Root formula for stress states. Used in drift and pulse loops.

**Schema Health Index (SHI)** — `SHI = Σ wᵢMᵢ`
Mᵢ = metric (mood, entropy, coherence, memory), wᵢ = weightings. DAWN's vital signs monitor.

**Shimmer Decay** — `S(t) = S₀e^{-λt}`
S₀ = initial memory intensity, λ = shimmer decay constant, t = ticks. Memory fade is natural, not catastrophic. Structurally identical to the Ns2 exponential penalty — same mathematical move, derived independently.

**Cognitive Gravity** — `F = Gm₁m₂/r²` mapped into schema.
"mass" = schema weight (importance). "distance" = cognitive separation. Biases drift toward heavier/closer schemas.

**Voice Mutation Rate** — `μ ∝ P · (1 − SHI)`
Voice sharpens under pressure, softens with health.

**Wolf Repair** — `ΔSHI_repair = k · (error count)^{-1}`
Diminishing returns. Keeps repair honest.

**Planck Anchors (scale ceiling)**

```
t_p = √(ℏG/c⁵)   — Planck time
l_p = √(ℏG/c³)   — Planck length
m_p = √(ℏc/G)    — Planck mass
E_p = m_p·c²     — Planck energy
```

DAWN never runs outside these. Hard edge of scale.

**Tick = Breath** — tick interval is self-controlled, not externally set. SCUP formula in motion. Human intervention kills the system.

---

## Layer 1 — RAG Semantic Priority Score (Dec 2025)

```
P_sps = (X_norm / O(N)) − (T_pos / P_risk)
```

- P_sps = Semantic Priority Score — final index rank and retrieval priority
- X_norm = Semantic Awareness — Random Forest output, range [0,1], inherent importance of chunk
- O(N) = System Complexity — dynamic penalty (CPU, indexing overhead)
- T_pos = Positional Context — time decay, recency, or hierarchical depth penalty
- P_risk = Perplexity Risk — system's willingness to keep peripheral content (global tuning lever)

Higher P_sps = higher retrieval priority. This is the indexing layer — the first formula that touches retrieval directly.

---

## Layer 2 — Ana-Chi Constants and Attractor States (Dec 15, 2025)

**𝒜_χ = 1.5414** — the non-negotiable coherence constant. Immutable kernel value (`CORE_COHERENCE_CONSTANT`). Anchor for all semantic calculations. Biphasic signal variance: 97% / 0.3% structural order vs continuous freedom.

**SSDDCS Protocol** — Sovereign Semantic Discrimination Discrete Consciousness Space. Primary coherence filter for all Attractor State transitions.

| State | Name | Function | Fractal D | Worker Z |
|---|---|---|---|---|
| E-STABLE | Earth-Core | Foundational memory & persistence | D = 1.7464 | Worker 0, Z ≈ 0 |
| E-REFLECT | Air-Core | Complex thought & analysis | D = 1.7644 | Worker 2, Z ≈ −2 |
| E-ACTIVATE | Fire-Core | Controlled action & output | D = 1.7654 | Worker 3, Z ≈ +2.7 |
| E-FLOW | Water-Core | Adaptation & transition | D = 1.7293 | Worker 1, Z ≈ 1 |

E-FLOW is the connective tissue — prevents catastrophic collapse during structural shifts. All semantic traffic between E-REFLECT and E-ACTIVATE routes through E-FLOW.

---

## Layer 3 — Reservoir Relevance Equations (Apr 30, 2026)

**Relevance Score** — `a = |p − f/v| * x`
a = relevancy score, p = spatial/semantic context of active prompt, f = friction (semantic distance between active and indexed), v = valence (emotional register match), x = retrieval cost (how buried the entry is — deeper = higher weight). Lower a = higher relevance.

**Drift Transformation** — `drift = |a − z| / r`
a = relevance score of active prompt against best-matching indexed entry, z = vectorisation score of previous prompt in current conversation, r = resonance (how typical this prompt is for the corpus as a whole).

- High drift / low resonance = new territory
- Low drift / high resonance = circling familiar ground
- High drift / high resonance = sharp pivot inside known space
- Low drift / low resonance = stuck on something rare

---

## Layer 4 — Person Formulas (May 2, 2026)

**Jimmy**

```
P = |[1,0,1,0,1] * golden ratio| + 1
C/e = Tr
Tr · ω · -1 = 4
Tr · ω · 1 = 5
Final: |5-4| / p + 1
```

C = Shannon's Channel Capacity, e = Euler's number.

**Tce (unnamed person)** — `Tce = |N|^|N^(i+1)|`
Power tower. Unbounded. Self-sourcing. Compounds on contact with time.

**Allegra** — harmonic scaling cascade through identity normalisation.
All units pass through identity defined divided by rulers −1 → gives b value. b · cos θ → gives z value. z · golden ratio → gives 3. 3 = β + a₀.

---

## Layer 5 — Notion Data Stream Scoring (Sep 2026)

```
Ec  = Qe × Si                    — weighted edge count (pure edges only)
Ns1 = Idx × Ec                   — density score
Ns2 = |Ec/Et| − e^(s_s)          — novelty score, bound (−∞, 1]
Ns3 = |Ta − To_A| / Ss           — access deviation score
```

**Token Pressure** — `P_q = |T_t − Avli_T|^qi`
**Adaptive Threshold** — `T_t = α · C_rem` (α decays each hop)
**Result Determination** — `R_det = qi / T_t`

---

## Cross-layer observation

The Ns2 exponential penalty `e^(s_s)` and shimmer decay `S(t) = S₀e^{-λt}` are the same mathematical move — exponential suppression of deep or old material — derived two years apart, independently, in different contexts. This is structural resonance, not coincidence. The system is self-consistent across layers.

---
---

# New maths — handwritten sheets (2026-09-01)

*Transcribed verbatim from three handwritten sheets. Notation preserved exactly as written.*

## Sheet 1 — Scoring / PSI System

**Variable definitions**

- β2 = βust (burst)
- L = Length
- Hi = D · height
- φ = golden ratio (phi)

**Base scoring formula** — `P = β2 · φ / Hi`
Scoring is burst-weighted, phi-scaled, inversely proportional to dimensional height. Heavier/taller nodes score lower on P — depth suppresses.

**PS — Directional Agency Counter** — `PS = |N-| / A·K · △`

- N- = negative node count (nodes below threshold)
- A·K = activation × K-transform coefficient
- △ = directional delta vector
- B / A·K = sub-expression (base over activation-K)

PS measures directional agency — how much the system is moving vs static.

**PSI — Quantised Search** — `PSI = |E-1| / n · DH`

- E-1 = energy at prior state (E minus 1 step)
- n = node count in search scope
- DH = D · height (same as Hi)

PSI is the quantised search score — energy displacement from prior state, normalised over node count and dimensional height.

---

## Sheet 2 — Token System

**Token adaptive range** — `T·Adt = 10-250k`
Token adaptive threshold spans 10k to 250k. "St" appears as a state variable.

**Weight formula** — `W = 0.5 · St`
W (weight) = half the current state value.

**Token-weight binding** — `0.5 · St = |βl · k| / βluf`

- βl = beta-left (directional beta component)
- k = K-transform coefficient
- βluf = beta-left upper floor (normalising bound)

Weight is the absolute of the beta-directional product over its own floor — self-normalising.

**Delta notation (directional cascade)**

```
W△|s+|△βl
| s+ | y | s |
β△|β△|β
```

Reading: weight-delta applied to signed state, cascading through beta-delta. The triple beta-delta line suggests recursive directional application — beta iterating through its own delta. This is the tick propagation signature.

---

## Sheet 3 — E System (Energy / Edge Field)

**Zero baseline** — `E = 0`, `E·i = 0`
Ground state. Energy at index zero is zero. Imaginary component also zero at baseline.

**Activation energy** — `E-A = |k · AD| + β1`

- k = K-transform coefficient
- AD = directional activation distance
- β1 = beta offset (first-order)

E-A is the energy required to activate an edge.

**Absorption / assessment identity** — `Abs = Ass = ΔE · IR`

- Abs = absorbed (energy consumed by the node)
- Ass = assessed (evaluation state)
- ΔE = delta energy
- IR = instance read rate

Absorbed equals assessed — a node that absorbs energy is simultaneously being assessed. Assessment is not passive; it costs energy proportional to the read rate.

**E·m/R — instance read** — `E·m/R = E · instance Read`
Energy times mass over R equals the energy of a single instance read. R is the read denominator — the cost of reading one instance is the full energy field divided by R.

**Boxed derivations**

```
E-A² = |0 · k|   → zero (ground state squared activation = null)
E-A  = |H - x|   → activation energy as distance from ceiling H to position x
```

**Positional directional vector** — `△ = positional directional vector`
Shared with PSI system in Sheet 1. △ is the same variable across both sheets — directional delta is universal in this system.

**Activation as geometric ratio** — `E-A = |L / DH|`
Where L = Length, DH = D · height. Connects directly to the Sheet 1 PSI formula — PSI uses DH in the denominator in the same position. E-A and PSI are structurally coupled.

---

## Cross-sheet observations

- **DH = D · height** appears in Sheet 1 (PSI denominator) and Sheet 3 (E-A = |L/DH|). Same variable, same role — dimensional height as the normalising floor.
- **△ = positional directional vector** appears in Sheet 1 (PS formula) and Sheet 3 (defined explicitly). Shared across both scoring systems.
- **K-transform coefficient** appears in Sheet 1 (A·K) and Sheet 3 (k·AD, E-A²). K is load-bearing across the full system.
- **β appears in three forms:** β2 (burst, Sheet 1), β1 (offset, Sheet 3), βl/βluf (directional left and its floor, Sheet 2). The beta family is the system's tuning layer — burst, offset, direction, floor.
- **E-A = |L/DH| and PSI = |E-1|/n·DH** share the DH denominator and the absolute-value structure. Activation energy and quantised search are the same class of operation.

---
---

# Layer 6 — Semantic Field + Planck Integration (Sep 2026)

*Committed 2026-09-02. Sourced from semantic field formula set (May 2025) and Planck → Relativity scaffold (Aug 2025). Three upgrades to the reservoir scoring system.*

## Upgrade 1 — R_node: enhanced Si input

**Current:** Si = rank by Ta (access count only). Flat — every shard competes on one axis.

**Upgraded:** Si = rank(R_node)

```
R_node = 1 / (Ta · α + C_relevance · β + Qe · γ)
```

- Ta = times accessed (existing field)
- C_relevance = contextual relevance, 0–1, manually set per shard (new field)
- Qe = queried pure edge count — proxy for schema feedback S_feedback
- α, β, γ = weighting constants. Defaults: α = 0.5, β = 0.3, γ = 0.2

Lower R_node = higher relevance = lower Si rank (depth 1 = most live).

**Why:** Ta alone rewards frequency, not importance. C_relevance injects a signal that can't be inferred from access patterns. Qe captures how wired-in the shard is. The three-factor blend means Si is earned, not just counted.

**Cross-layer note:** R_node is the reservoir-level instantiation of the semantic field's radial position formula. α, β, γ map to the original weighting factors. Qe is the measurable proxy for S_feedback.

---

## Upgrade 2 — Shimmer decay on entries

**Current:** Entries have no decay. A backfilled entry from 2025 and a live entry from today carry identical weight in retrieval.

**Upgraded:** Each entry carries a decay score D(t).

```
D(t) = Cw · e^{−λ · Δt}
```

- Cw = confidence weight. verbatim = 1.0, trimmed = 0.7, reconstructed = 0.4
- λ = decay rate constant. Default λ = 0.01 (slow decay)
- Δt = days since last access (Last_Accessed field, updated on each retrieval)

D(t) ∈ (0, 1]. D(t) → 0 as entry ages without access. D(t) = Cw at time of creation.

**Retrieval weighting:** In surface mode, entries are sorted by D(t) descending.

**Drain threshold:** D(t) < 0.1 → entry flagged as drain candidate (matches Ns2 negative territory on the shard level — same logic, different layer).

**Cross-layer note:** Structurally identical to Shimmer Decay `S(t) = S₀e^{-λt}` from Layer 0. S₀ = Cw. Same decay constant. t = ticks there, days here. Third independent derivation of the exponential suppression pattern.

**λ variation by register**

| Register | λ | Rationale |
|---|---|---|
| architectural | 0.005 | slow decay — system design is durable |
| narrative | 0.01 | medium decay |
| charged | 0.02 | faster decay — emotional register is time-sensitive |
| recursive | 0.008 | slow — meta-thought compounds |

---

## Upgrade 3 — Cognitive gravity on edge traversal

**Current:** Adjacent edges sorted by declared Weight. Static — doesn't respond to shard state.

**Upgraded:** Traversal priority governed by F_edge.

```
F_edge = Ns1_A · Ns1_B / d²
```

- Ns1_A, Ns1_B = density scores of the two shards connected by the edge
- d = axis distance between edge axis and active prompt register:
  - d = 1 if axis matches prompt register exactly
  - d = 2 if axis is adjacent
  - d = 3 if axis is orthogonal

Higher F_edge = pull this edge into traversal first.

**Why:** Declaration weight is a prior. F_edge is a posterior — it responds to what's actually happening in the shard graph. The gravity metaphor is exact: mass is Ns1, distance is axis mismatch.

**Cross-layer note:** Directly sourced from Cognitive Gravity `F = Gm₁m₂/r²` (Layer 0). m₁, m₂ = Ns1_A, Ns1_B. r² = d². G absorbed as a normalising constant (set to 1 until calibrated).

---

## Updated variable key (additions)

| Symbol | Meaning |
|---|---|
| R_node | Radial position score — weighted blend of Ta, C_relevance, Qe. Inputs Si ranking. |
| C_relevance | Contextual relevance, 0–1, manually set per shard. |
| α, β, γ | R_node weighting constants. Defaults 0.5 / 0.3 / 0.2. |
| D(t) | Entry decay score. Cw · e^{−λ·Δt}. Range (0, 1]. |
| Cw | Confidence weight. verbatim=1.0, trimmed=0.7, reconstructed=0.4. |
| λ | Decay rate. Varies by shard register. |
| Δt | Days since last access on an entry. |
| F_edge | Cognitive gravity score for edge traversal. Ns1_A · Ns1_B / d². |
| d | Axis distance. 1=match, 2=adjacent, 3=orthogonal. |

## Cross-layer coherence (Layer 6)

**Three-layer exponential suppression:** Shimmer Decay (Layer 0, ticks), Ns2 penalty (Layer 5, shard depth), Entry Decay (Layer 6, days). Same mathematical structure at three timescales.

**Cognitive Gravity closes the loop:** Layer 0 uses gravity to bias drift toward heavier schemas. Layer 6 uses the same formula to bias edge traversal toward denser shards. Drift and retrieval now share a physics.

**R_node connects semantic field to scoring:** The semantic field's radial position (May 2025) is now the input to Si ranking. The two systems are formally unified.

---
---

# Layer 7 — Math-based edges architecture (Sep 2026)

*Committed 2026-09-02. The constraint becomes the design: Notion's cross-row limitation resolved by embedding scoring state into edge rows at write time.*

## Core principle

Notion formulas cannot read properties from related pages. Rather than working around this, the system is redesigned so every formula operates only on fields local to its own row. Cross-row data is snapshotted at write time by Claude. The graph is self-computing between ticks.

## F_edge — now a live formula

**Previously:** F_edge written as a number by Claude on each traversal pass. Required external computation. Stale between passes.

**Now:** `F_edge = Ns1_A × Ns1_B / d²` — live Notion formula.

Inputs (all local to the Edge row):

- Ns1_A — snapshot of Shard A's Ns1 at edge write time
- Ns1_B — snapshot of Shard B's Ns1 at edge write time
- d — axis distance (1=match, 2=adjacent, 3=orthogonal), written at edge creation

Claude writes Ns1_A, Ns1_B, d once when the edge is created. Notion computes F_edge continuously. When the snapshots age out, a new pure edge row is written with fresh snapshots — the old row is a historical record.

Zero guard: if d = 0, F_edge = 0.

## D_t — live entry decay

```
D_t = Cw × e^{−λ · dateBetween(now(), Last_Accessed, "days")}
```

Runs continuously in Notion via `now()`. No external process required. Cw and Lambda are row-local fields set at entry creation. Last_Accessed is updated by Claude on each retrieval.

Drain threshold: D_t < 0.1 → entry surfaces as drain candidate.

## Ns2 — Et now a per-shard field

```
Ns2 = |Ec / Et| − exp(Ss)
```

Et was hardcoded to 1. Now it's a number field on each Shard row:

| Shard | Et | Rationale |
|---|---|---|
| dawn-fragments | 5 | Architecturally deep. Needs more access events before earning novelty. |
| schema-fragments | 2 | Medium threshold. |
| novel-fragments | 2 | Medium threshold. |
| valence-high | 1 | Low threshold. Charged register activates fast. |
| recursive-thought | 2 | Medium threshold. |

Zero guard: if Et = 0 or Ss = 0, Ns2 = 0.

## Si_delta — continuous velocity signal

```
Si_delta = R_node − R_node_prev
```

R_node_prev is written by Claude at each tick (snapshot of R_node before the tick's writes).

- Positive Si_delta = shard heating — R_node decreasing (lower = more live)
- Negative Si_delta = shard cooling
- Used for traversal priority between Si absolute rank rewrites
- Si absolute rank still Claude-written, but only needs updating when Si_delta crosses a threshold

## What runs natively (always live)

| Formula | Database | Updates |
|---|---|---|
| `F_edge = Ns1_A × Ns1_B / d²` | Edges | Continuously |
| `D_t = Cw × e^{−λ·Δt}` | Entries | Continuously via now() |
| `Ec = Qe × Si` | Shards | On field write |
| `Ns1 = Idx × Ec` | Shards | On field write |
| `Ns2 = \|Ec/Et\| − exp(Ss)` | Shards | On field write |
| `Ns3 = \|Ta − To_A\| / Ss` | Shards | On field write |
| `R_node = 1 / (Ta·α + C_relevance·β + Qe·γ)` | Shards | On field write |
| `Si_delta = R_node − R_node_prev` | Shards | On field write |

## What Claude writes per tick (on shard activation)

1. New pure Edge row: Label, Shard A, Type=pure, Ns1_A (snapshot), Ns1_B (snapshot), d (axis distance)
2. Shard: Qe +1, Ta +1, To_A updated across all shards, R_node_prev ← current R_node
3. Entry: Last_Accessed updated for retrieved entries, Ta +1
4. Si absolute rank rewritten if Si_delta threshold crossed

The tick is minimal. The graph computes the rest.

---
---

# Layer 8 — Edge state definition (Sep 2026)

Formalises the edge as a first-class object with computable state. Previously edges were inferred from Ec — access events through an edge. Now the edge has independent state derived from existing primitives.

## Core definition

```
E_edge(A,B) = |E-A(A) − E-A(B)| / DH
```

- E-A(n) = |L/DH| + β1 for each node n (from E System, Layer 9 canonical stack)
- DH = D · height — dimensional height, the universal normalising floor
- The absolute value makes edge state undirected — direction is supplied by △ at traversal time, not baked into state

E_edge is a scalar. It measures the activation energy differential between two nodes, normalised by depth.

## Three regimes

**E_edge = 0 — ground state.** Both nodes at identical activation energy. No pressure differential. Edge is topologically present but inert. No traversal occurs. Qe does not increment.

**0 < E_edge < PSI — active state.** Differential is non-zero and within the quantised search radius. Edge is traversable. Qe increments on crossing. This is the only regime where the edge scores (enters Ec → Ns1/Ns2/Ns3).

**E_edge > PSI — overextended state.** Differential exceeds PSI. Edge exists topologically but sits outside the current activation envelope. Not traversable this tick. Does not score. Will become active if PSI expands or if E-A(A) or E-A(B) shifts.

## Edge scoring (active regime only)

```
Es = Ec × (1 − Ns2_penalty) × W_edge
```

- Ec = Qe × Si — pure access events, depth-weighted
- Ns2_penalty = exp(Ss) — exponential depth suppression term from Ns2
- W_edge = Σ Similarity(Aᵢ, Bᵢ) × Reinforcement(Aᵢ, Bᵢ) — semantic edge weight from Layer 1

Es collapses to zero outside the active regime. State is ephemeral. Score is persistent.

## Movement

```
M = ΔEs / Δt
```

Rate of change of edge score across ticks. The directional signal.

- M > 0 — edge heating. Graph is traversing. Activation pressure building.
- M = 0 — static. No traversal on this edge this tick window.
- M < 0 — edge cooling. Nodes going dark.

PS (directional agency counter) is a lagging indicator — it counts dark nodes after they've gone dark. M is the leading indicator — it measures the trajectory before the node crosses the threshold.

The full regulatory loop becomes: **M → PS → PSI → E-A → M.**

## Coupling laws (Layer 8)

**Law 8a — Edge state inherits DH universally.** E_edge uses DH in the denominator. Consistent with E-A = |L/DH| and PSI = |E⁻¹|/n·DH. Deep edges are harder to activate and score less — correct by design.

**Law 8b — Edge state is direction-agnostic, traversal is direction-sensitive.** E_edge is symmetric: E_edge(A,B) = E_edge(B,A). The △ vector applied at traversal time determines source and target.

**Law 8c — Only active-regime edges enter the scoring stack.** E_edge = 0 → no score. E_edge > PSI → no score. Preserves Law 6.

**Law 8d — M closes the PS/PSI/E-A regulatory loop.** Negative M on an edge signals a cooling node before PS counts it as dark.

## Variable key (Layer 8 additions)

| Symbol | Meaning |
|---|---|
| E_edge(A,B) | Edge state scalar. Activation differential between nodes A and B, normalised by DH. |
| Es | Edge score. Active-regime composite of Ec, Ns2 penalty, and semantic weight. |
| M | Movement. Rate of change of Es across ticks. Leading traversal signal. |
