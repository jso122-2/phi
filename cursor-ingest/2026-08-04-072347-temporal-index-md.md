# temporal-index.md

#doc #md

> path: temporal-index.md  
> ext: .md  

---

# temporal-index

#math #code

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
activation[h][k] = activation_0 × memory_de

---

## Semantic links

→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]
→ [[temporal-index]]
→ [[harmonic-index]]
→ [[temporal-index]]
→ [[harmonic-index]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-source-sims-temporal-md]]
→ [[cursor-ingest/2026-08-04-072347-harmonic-index-md]]
→ [[cursor-ingest/2026-08-04-072347-sims-temporal-py]]
→ [[cursor-ingest/2026-08-04-072347-sims-harmonic-py]]
→ [[cursor-ingest/2026-08-04-072347-source-sims-harmonic-md]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
