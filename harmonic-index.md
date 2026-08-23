# harmonic-index

#math #code #hub

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
- Quarter-ring (d = 0.5): c = 0 → neutral
- Far shards (d > 0.5): c < 0 → **inhibitory** (lateral inhibition)
- Antipodal (d = 1): c = −1 → maximum inhibition
- **All-to-all** coupling in ONE hop → path space = N·(N−1)^k total paths vs 2^k for local.

#### Eigenvalue spectrum (verified 2026-08-05, N=8, κ=0.15)

The cosine kernel K is a circulant matrix with exactly two distinct eigenvalues:

```
λ_K = +3   (2-fold degenerate)  →  update eigenvalue  1 + κ·3  = 1.45  ← GROWS
λ_K = −1   (6-fold degenerate)  →  update eigenvalue  1 + κ·(−1) = 0.85 ← decays
```

The "dissipative" label in the code refers only to the λ=−1 eigenspace (the uniform / m=0 mode — total activation). The **λ=+3 eigenmodes grow by 45% per step** and dominate any initial condition that has non-zero projection onto them.

Practical consequence: any non-uniform injection (including the CSS `101010` shard pattern) projects onto the growing eigenmodes and will **amplify without bound** unless externally clipped. The TicketClipper is the stability mechanism — it is not diagnostic infrastructure, it is the amplitude control that prevents the λ=3 modes from diverging.

**Correction:** An earlier analysis claimed `101010` (shards 1, 3, 5 active) is a fixed point of isometric propagation via a neutral-zone argument (d=2 between stride-2 shards → c=0). This is wrong. The shards 1 and 5 are antipodal (d=4 → c=−1) and maximally inhibit each other; the `101010` pattern has |projection|=0.35 onto both λ=3 eigenvectors and is therefore unstable. Verified empirically: after 10 isometric steps from [0,1,0,1,0,1,0,0], shard amplitudes reach ±10 while the total decays to ~0.59.

#### Path-space expansion (N=8)

| k hops | local 2^k | isometric 8·7^k | ratio |
|---|---|---|---|
| 1 | 2 | 56 | 28× |
| 6 | 64 | 941,192 | 14,706× |
| 10 | 1,024 | 282,475,249 | 275,855× |
| 13 | 8,192 | ~6.85 billion | ~836,000× |

At k=13 hops the isometric cosine ring reaches **~6.85 billion** possible routing
paths — the "6547 million" regime — vs 6 maximum diameter hops under local propagation.

#### Ticket clipping

When `mode="isometric"` the `TicketClipper` records every hub passage above threshold:

```python
from sims.harmonic import TicketClipper
clipper = TicketClipper(index, threshold=0.01)
clips = clipper.propagate_and_clip(steps=5, mode="isometric")
journey = clipper.journey_summary()
# → {"hubs_clipped": ["HOME", "MATH", ...], "total_clips": 12, ...}
```

- κ = **0.15** (coupling constant)
- Topology is a **ring** (shard 0 and shard 7 are neighbours via modular wrap)

---

## Injection

When a trajectory from [[attractors]] completes, its final |x| is mapped to the
nearest basin centre and that shard's activation is incremented by 1.0:

```
nearest = argmin_i |basin_centre(i) − |final_x||
shards[nearest].activation += 1.0
```

Both ±α map to the same shard (index 0, harmonic 1) because |±1.96| = 1.96.

---

## Python API

```python
from sims.harmonic import HarmonicIndex, HarmonicShard, LocalPropagator, TicketClipper

idx = HarmonicIndex(n_harmonics=8, coupling=0.15)
idx.inject(shard_index=0, value=1.0)           # direct injection
idx.inject_from_trajectory_final(final_x)      # map from trajectory
idx.propagate(steps=3)                         # advance 3 cycles (local)
idx.propagate(steps=3, mode="isometric")       # isometric cosine decay + ticket clip
state = idx.state()                            # full serialisable snapshot
peak = idx.peak_shard()                        # HarmonicShard with max activation
idx.reset()                                    # zero everything

# Ticket clipping
clipper = TicketClipper(idx, threshold=0.01)
clips = clipper.propagate_and_clip(steps=5, mode="isometric")
journey = clipper.journey_summary()
```

---

## Run it now

```
/index                → current state of all 8 shards
/propagate 5          → advance 5 wave cycles (local mode)
/propagate 5 isometric → isometric cosine decay, returns path_space + ticket_journey
/inject 0 2.0         → add 2.0 activation to shard 0
/reset                → zero all activations
```

---

## Auto-linked

→ [[live-state]]
→ [[COMMANDS]]
→ [[psspps]]
→ [[CODE]]
→ [[2026-07-13-120800-dawn-physics-scaffold-and-mycelial-layer-context-dump]]
→ [[dawn-physics-scaffold]]

→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]
→ [[cairrn]]
→ [[2026-07-13-integrate-ana-chi-constant-modulate-cairrn-stable-states]]
→ [[ana-chi]]
→ [[hub-classifier]]

→ [[sessions]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[README]]
→ [[graph]]
→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]
→ [[2026-07-13-095004-cairrnify-the-mcp-server-fix-dom-queue-open]]

→ [[logger]]
→ [[2026-07-16-011935-cairrn-cairrn-worker-system]]
→ [[worker]]
→ [[git-log]]

→ [[lambert-w]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-16-011935-spotify-rip-mcp-server-global-agent-contract]]
→ [[2026-07-16-011935-slash-commands-spotify-rip]]
→ [[2026-07-13-040738-2026-07-13t14-07-38-557-10-00]]
→ [[2026-02-26-132809-2026-02-27t00-28-10-015-11-00]]

→ [[scratch]]
→ [[sims-harmonic]]
→ [[2026-07-17T02-45-15Z-OctopusTracer v1 — Full Integration Summary]]
→ [[2026-01-15-080152-2026-01-15t21-30-47-349-11-00]]
→ [[2026-06-04-124832-2026-06-04t22-48-34-493-10-00]]
→ [[2025-10-03-120206-2025-10-03t22-04-36-490-10-00]]
