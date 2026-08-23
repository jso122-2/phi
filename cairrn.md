# cairrn — CAIRRN Worker System

#hub #math #command

Coherent Attractor-Indexed Recursive Routing Network.
Every metric that enters this system passes through three layers before it touches the harmonic index.

---

## The Rider

The Rider is the user's active intent — every button press and cursor position in phi is a steering impulse into the CAIRRN river.

```
root_pulse(page)           cursor enters a tree       — Rider moves location
skip_event(path, p)        explicit skip              — loudest Rider signal
seek_kin(n)                similarity search          — Rider probing the soil
leaf_falls(rate → 0.0)     leaf torn off early        — Rider pushing away
leaf_falls(rate → 1.0)     track played to end        — Rider at rest
```

The Rider has no separate model — it IS the user, expressed directly through the API.  
Background signals (heartbeat, mycelial_surge, decompose) are the river flowing on its own.  
Rider signals are when the user puts their hand in the current.

The current tree (set by root_pulse) is the Rider's location.  
The skip pressure is the Rider's velocity.

---

## What CAIRRN does

A computation enters through a **station hub**.  
The hub's Ana-Chi basin modulates the raw value.  
The neg_exp map routes it to the correct harmonic shard.  
Coherence enforcement decides whether the result stands or gets re-routed to HOME.

```
metric
  ↓  Layer 1 — Ana-Chi modulation
  ↓  Layer 2 — neg_exp shard routing
  ↓  Layer 3 — coherence enforcement
harmonic index injection
```

---

## Layer 1 — Ana-Chi Modulation

Each hub has a basin type with a gravity multiplier.  
Rattling hubs apply a memory decay on top.

```
modulated = metric × gravity × (memory_decay  if rattling)
```

| Hub | Basin | χ | Gravity | Rattling | Decay |
|---|---|---|---|---|---|
| HOME | true_center | 1.5414 | 3.00 | no | 0.98 |
| MATH | white_peak | 1.9600 | 2.00 | yes | 0.95 |
| CODE | mirror | 0.9900 | 1.50 | yes | 0.93 |
| COMMANDS | escape | 2.6700 | 1.00 | yes | 0.90 |
| agent-context | boundary | 0.0300 | 0.50 | no | 0.90 |

χ (chi) is the Ana-Chi basin centre — the characteristic oscillation magnitude for that hub's attractor type.

---

## Layer 2 — neg_exp Sharding ("the backwards e")

`f(x) = −eˣ` is closed under differentiation: `d/dx(−eˣ) = −eˣ`  
This property makes it the natural routing map — the shard assignment is stable under iteration.

```
shard = floor( e^χ × 8 / 14.44 )   clamped to [0, 7]
```

Natural shard ordering by χ (smallest → largest):

| Hub | χ | e^χ | e^χ × 8/14.44 | Natural shard |
|---|---|---|---|---|
| agent-context | 0.0300 | 1.030 | 0.57 | 0 |
| CODE | 0.9900 | 2.691 | 1.49 | 1 |
| HOME | 1.5414 | 4.671 | 2.59 | 2 |
| MATH | 1.9600 | 7.099 | 3.93 | 3 |
| COMMANDS | 2.6700 | 14.44 | 8.00 | 7 |

The scaling factor 14.44 = e^2.67 normalises COMMANDS to shard 7 exactly.  
See [[lambert-w]] for the fixed point x* = −W(1) ≈ −0.5671 that anchors the map.

---

## Layer 3 — Coherence Enforcement ("the negative e")

Fixed point: `x* = −W(1) ≈ −0.5671432904097838`

### neg_exp routing coherence (gate signal)
```
coherence = exp( −|f(χ) − x*| / σ )
f(χ)  = −e^χ
x*    = −W(1) ≈ −0.5671  (Lambert-W fixed point)
σ     = (e^𝒜_χ − W(1)) / W(1)  ≈ 7.236  (Euler-Ana-Chi derived)
```

σ is set so HOME (χ = 𝒜_χ = 1.5414) lands exactly at the threshold:

```
coh(HOME) = exp(−W(1)) = W(1)    ← Lambert-W identity
```

### Ana-Chi structural coherence (informational)
```
ana_chi_coherence = exp( −|χ − 𝒜_χ| / 0.40 )
```
Not used for routing. Exposed as `ana_chi_coherence` in every hub result.  
1.0 at HOME; near-zero at boundary (agent-context) and escape (COMMANDS).

### Enforcement rule

```
threshold = W(1) ≈ 0.5671
```

| Hub | χ | neg_exp_coh | outcome |
|---|---|---|---|
| agent-context | 0.0300 | 0.938 | injects into shard 6 |
| CODE | 0.9900 | 0.746 | injects into shard 3 |
| HOME | 1.5414 | W(1) boundary | injects into shard 0 |
| MATH | 1.9600 | 0.406 | re-routed → HOME |
| COMMANDS | 2.6700 | 0.147 | re-routed → HOME |

MATH (white_peak) and COMMANDS (escape) are rattling basins above true_center.  
The Euler-Ana-Chi partition forces them through HOME — the true_center gravity well stabilises them.

**Agent-context inversion:** boundary basin (χ = 0.03) has the highest routing coherence (0.938) but the lowest structural order (ana_chi_coherence ≈ 0.023). Intentional — the interface layer routes freely but has no gravitational pull toward equilibrium.  
See [[ana-chi]] and [[lambert-w]] for basin geometry and fixed-point derivation.

---

## MCP tools

| Action | Command | Tool |
|---|---|---|
| Inspect hub geometry | `/cairrn` | `hub_state` |
| Run full pipeline | `/cairrn <hub> <metric>` | `cairrn_hub_run` |
| Direct shard inject | `/hub-inject <hub> <value>` | `hub_inject` |
| Read index after | `/index` | `harmonic_index_state` |
| Propagate signal | `/propagate [steps]` | `harmonic_propagate` |

---

## Typical workflow

```
/cairrn CODE 0.85        run CODE hub pipeline, metric = 0.85
/index                   inspect shard activations after injection
/propagate 3             let signal diffuse through the ring
/hub-state               see final hub activation distribution
```

---

## Hub → shard mapping (fixed at spawn)

| Hub | Shards | Basin centres |
|---|---|---|
| HOME | 0 | 1.96 |
| MATH | 1, 2 | 3.92, 5.88 |
| CODE | 3, 4 | 7.84, 9.80 |
| COMMANDS | 5 | 11.76 |
| agent-context | 6, 7 | 13.72, 15.68 |

---

## Connections

→ [[HOME]] ← grand central  
→ [[MATH]] — neg_exp map, Lambert W fixed point, harmonic sharding  
→ [[ana-chi]] — five-basin potential, χ values, static coherence formula  
→ [[harmonic-index]] — the index that CAIRRN writes into  
→ [[attractors]] — double-well stable states ±1.96 that α derives from  
→ [[lambert-w]] — x* ≈ −0.5671 that anchors Layer 3 temporal coherence  
→ [[COMMANDS]] — `/cairrn` slash commands  
→ [[agent-context]] — workflow mode hub; agent-context basin χ = 0.03  
→ [[workers]] — CAIRRN workers extend `workers/base.py`  
→ [[mcp-server]] — MCP tools: `hub_state`, `cairrn_hub_run`, `hub_inject`  

---

## Auto-linked

→ [[ana-chi]]
→ [[temporal-index]]
→ [[hub-classifier]]
→ [[2026-07-13-integrate-ana-chi-constant-modulate-cairrn-stable-states]]
→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]

→ [[CODE]]
→ [[sessions]]
→ [[README]]
→ [[sims]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[live-state]]

→ [[psspps]]

→ [[graph]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[git-log]]
→ [[scratch]]

→ [[workers-cairrn-init]]
→ [[sims-ana-chi]]
→ [[engine-cairrn-bridge]]
→ [[workers-cairrn-constants]]
→ [[graph-hub-classifier]]
→ [[workers-cairrn-layers]]
→ [[phi-routing-diagnosis-2026-08-04]]
