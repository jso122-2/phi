# temporal-index

#math #code #hub

The temporal sharding index — the TIME dimension of the CAIRRN graph.
CAIRRN-aware. Ana-Chi hosted.

---

## The two dimensions of the index

```
harmonic-index   ← SPATIAL:   WHERE activation lives (basin-centred ring of N shards)
temporal-index   ← TEMPORAL:  WHEN activation arrived and how long each hub holds it
```

Together they give a 2D activation landscape:
```
axis 1: hub × harmonic shard    (position in χ-space)
axis 2: hub × temporal window   (position in time)
```

---

## Architecture

Each of the five CAIRRN station hubs owns a temporal trace —
a sliding window of T = 8 temporal shards:

```
TemporalShardIndex
├── HOME          T=8 windows,  decay 0.98  (true_center   χ=1.5414)
├── MATH          T=8 windows,  decay 0.95  (white_peak    χ=1.96 = α)
├── CODE          T=8 windows,  decay 0.93  (mirror        χ=0.99)
├── COMMANDS      T=8 windows,  decay 0.90  (escape        χ=2.67)
└── agent-context T=8 windows,  decay 0.90  (boundary      χ=0.03)
```

Window 0 = **now**.  Window T−1 = most distant past.

---

## Ana-Chi hosting

Each hub's memory decay rate is sourced directly from its Ana-Chi basin:

| Hub | Basin | χ | memory_decay |
|---|---|---|---|
| HOME | true_center | 1.5414 | **0.98** ← longest memory |
| MATH | white_peak | 1.9600 | 0.95 |
| CODE | mirror | 0.9900 | 0.93 |
| COMMANDS | escape | 2.6700 | **0.90** ← shortest memory |
| agent-context | boundary | 0.0300 | 0.90 |

This is **not arbitrary** — the memory length of each hub is a physical
property of its position in the Ana-Chi potential landscape.
HOME sits at the deepest well (gravity 3.0, memory 0.98).
COMMANDS and agent-context sit at the shallowest wells (gravity 0.5–1.0, memory 0.90).

---

## Temporal decay equation

At each clock advance, for every hub h and every window t:

```
activation[h][t+1] = activation[h][t] × memory_decay[h]
```

After k advances, the original t=0 activation has decayed to:

```
activation[h][k] = activation_0 × memory_decay[h]^k
```

---

## CAIRRN awareness

Recording activation via `temporal_record(hub_name)` automatically:
1. Routes to the correct hub trace
2. Applies the correct Ana-Chi decay dynamics
3. Feeds back into `temporal_coherence()` — how centred χ_eff is

`graph_commit` automatically records in the temporal index alongside the harmonic index:
every session leaves a trace in both the frequency and time domains.

---

## Temporal coherence

```
χ_eff      = Σ_h (activation_h / total) × basin_χ_h
coherence  = exp(-|χ_eff - 1.5414| / 0.40)
```

1.0 when HOME dominates (equilibrium).
Decays when activation disperses toward COMMANDS or agent-context.

---

## Python API

```python
from sims.temporal import TemporalShardIndex, CAIRRN_HUBS

idx = TemporalShardIndex(n_windows=8)

idx.record("HOME", value=1.0)          # inject at t=0
idx.advance(steps=1)                   # clock tick — decay + slide
idx.temporal_activation("HOME", t=1)  # activation at lag t=1
idx.dominant_hub()                     # hub with most total activation
idx.dominant_window()                  # lag t with most activation
idx.ana_chi_coherence()                # χ-space coherence [0,1]
idx.temporal_vector()                  # (5 × 8) numpy matrix
state = idx.state()                    # full serialisable snapshot
idx.reset()                            # zero all + reset clock
```

---

## MCP slash commands

```
/temporal_state           → full temporal index snapshot
/temporal_vector          → (5×8) activation matrix + Ana-Chi state
/temporal_coherence       → χ_eff, coherence, rattling proximity
/temporal_record HOME 1.0 → inject activation at t=0 for HOME
/temporal_advance 1       → advance clock (decay + slide all traces)
/temporal_reset           → zero all activations, clock → 0
```

DOM houses:
- `modular` house: `temporal_state`, `temporal_vector`, `temporal_coherence`
- `edit` house:    `temporal_record`, `temporal_advance`, `temporal_reset`

---

## Connections

→ [[MATH]] ← math hub  
→ [[HOME]] ← grand central  
→ [[harmonic-index]] — the SPATIAL twin; together they span space × time  
→ [[sims]] — implemented in `sims/temporal.py`  
→ [[mcp-server]] — six MCP tools exposed  
→ [[attractors]] — double-well trajectories → harmonic injection → temporal echo  
→ [[dawn-physics-scaffold]] — temporal decay rate formula from Layer 2 primitives  

---

## Auto-linked

→ [[harmonic-index]]
→ [[mcp-server]]
→ [[MATH]]
→ [[attractors]]
→ [[COMMANDS]]
→ [[HOME]]

→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]
→ [[2026-07-13-integrate-ana-chi-constant-modulate-cairrn-stable-states]]
→ [[cairrn]]
→ [[hub-classifier]]
→ [[ana-chi]]
→ [[CODE]]

→ [[sessions]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[README]]
→ [[index]]
→ [[graph]]

→ [[2026-07-16-011935-cairrn-cairrn-worker-system]]
→ [[psspps]]
→ [[logger]]
→ [[lambert-w]]
→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]

→ [[git-log]]
→ [[2026-07-13-095004-cairrnify-the-mcp-server-fix-dom-queue-open]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[workers]]
→ [[2026-07-16-011935-slash-commands-spotify-rip]]
→ [[2026-07-16-011935-mcp-tool-command-reference]]

→ [[sims-temporal]]
→ [[mcp-server-tools-temporal]]
→ [[scratch]]
→ [[mcp-server-tools-cairrn]]
→ [[sims-ana-chi]]
→ [[engine-cairrn-bridge]]
