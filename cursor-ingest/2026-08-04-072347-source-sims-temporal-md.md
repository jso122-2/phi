# source / sims-temporal.md

#doc #md

> path: source/sims-temporal.md  
> ext: .md  

---

# sims/temporal

#code #module #sims #math

> source_path: sims/temporal.py  
> package: sims  
> module: sims/temporal  
> hub: MATH  
> created_ts:   

---

**Package:** `sims`  
**Module:** `sims/temporal`  
**Source:** `sims/temporal.py`

Temporal sharding index — CAIRRN-aware, Ana-Chi hosted.

The temporal index is the TIME dimension of the CAIRRN graph.
While the harmonic index (sims/harmonic.py) is the SPATIAL dimension
— where activation lives across harmonic basin centres — the temporal
index tracks WHEN activation arrived and how long each hub holds it.

Architecture
------------
Each of the five CAIRRN station hubs owns a temporal trace: a sliding
window of T time-windows (temporal shards) representing lags
t=0 (now) through t=T-1 (most distant past):

    TemporalShardIndex
    ├── HOME          T windows, decay 0.98  (true_center — longest memory)
    ├── MATH          T windows, decay 0.95  (white_peak)
    ├── CODE          T windows, decay 0.93  (mirror)
    ├── COMMANDS      T windows, decay 0.90  (escape)
    └── agent-context T windows, decay 0.90  (boundary)

Ana-Chi hosting
---------------
Each hub's memory decay rate is NOT arbitrary — it is governed by its
mapped Ana-Chi basin's `memory_decay` field:

    Hub           Basin         χ        memory_decay
    ──────────    ──────────    ──────   ────────────
    HOME          true_center   1.5414   0.98   ← equilibrium, longest memory
    MATH          white_peak    1.9600   0.95   ← singularity = ALPHA
    CODE          mirror        0.9900   0.93
    COMMANDS      escape        2.6700   0.90   ← rapid action, short memory
    agent-context boundary      0.0300   0.90   ← interface layer, short memory

At each clock advance, every activation in every temporal shard decays:

    activation[hub][t+1] = activation[hub][t] × memory_decay[hub]

CAIRRN awareness
----------------
The five hubs are structurally first-class.  Recording activation via
`record(hub_name, value)` automatically routes to th

---

## Semantic links

→ [[sims-temporal]]
→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]
→ [[temporal-index]]
→ [[harmonic-index]]
→ [[harmonic-index]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-sims-temporal-py]]
→ [[cursor-ingest/2026-08-04-072347-harmonic-index-md]]
→ [[cursor-ingest/2026-08-04-072347-temporal-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-sims-harmonic-md]]
→ [[cursor-ingest/2026-08-04-072347-sims-harmonic-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
