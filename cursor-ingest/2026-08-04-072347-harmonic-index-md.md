# harmonic-index.md

#doc #md

> path: harmonic-index.md  
> ext: .md  

---

# harmonic-index

#math #code

The harmonically-sharded propagation index — a ring of activation nodes
centred on multiples of α = 1.96.

---

## Connections

→ [[MATH]] ← math hub  
→ [[HOME]] ← grand central  
→ [[attractors]] — trajectories feed into this index  
→ [[sims]] — implemented in `sims/harmonic.py`  
→ [[temporal-index]] — the TIME dimension: CAIRRN-aware, Ana-Chi hosted temporal sharding  
→ [[mcp-server]] — exposed as `harmonic_index_state`, `harmonic_propagate`, `harmonic_inject`, `harmonic_reset`, `temporal_state`, `temporal_vector`, `temporal_coherence`, `temporal_record`, `temporal_advance`, `temporal_reset`  
→ [[workers]] — workers run the sims that populate this index  

---

## Architecture

A ring of N shards.  Shard i is centred on harmonic (i+1)·α:

```
basin_centre(i) = (i + 1) · α = (i + 1) · 1.96
```

### Shard ring (N = 8)

| Shard i | Harmonic | Basin centre |
|---|---|---|
| 0 | 1 | 1.96 |
| 1 | 2 | 3.92 |
| 2 | 3 | 5.88 |
| 3 | 4 | 7.84 |
| 4 | 5 | 9.80 |
| 5 | 6 | 11.76 |
| 6 | 7 | 13.72 |
| 7 | 8 | 15.68 |

---

## Propagation modes

Three propagators are available via `/propagate [steps] [mode]`:

### `local` — discrete wave diffusion (default)
```
a_i(t+1) = a_i(t) + κ·[a_{i−1}(t) + a_{i+1}(t) − 2·a_i(t)]
```
- κ < 0.5 for stability. Nearest-neighbour only. Total activation conserved.
- Path space: **2^k** per source after k steps (diameter = 4 hops max).

### `resonance` — exponential cosine resonance sharing
```
gate    = −cos(π · a_peak / A)           dominance ratio
shape_i = −cos(π · ring_dist(i, peak))   spatial kernel
w_i     = exp(gate · shape_i)            resonance weight
```
Hotspot donates κ·a_peak; receivers gain proportionally. Total conserved.

### `isometric` — TRUE isometric cosine-modulated decay ← **new**
```
c(d) = cos(π · d)   d = ring_dist / (N/2) ∈ [0, 1]
Δa_i = κ · Σ_{j≠i} c(d(i,j)) · a_j
```
- **Direct bipolar cosine kernel** — no exponential wrapping.
- Near shards (d < 0.5): c > 0 → excitatory
- Quarte

---

## Semantic links

→ [[harmonic-index]]
→ [[harmonic-index]]
→ [[sims-harmonic]]
→ [[sims-temporal]]
→ [[mcp-server-tools-harmonic]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-sims-harmonic-py]]
→ [[cursor-ingest/2026-08-04-072347-source-sims-temporal-md]]
→ [[cursor-ingest/2026-08-04-072347-temporal-index-md]]
→ [[cursor-ingest/2026-08-04-072347-source-sims-harmonic-md]]
→ [[cursor-ingest/2026-08-04-072347-sims-temporal-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
