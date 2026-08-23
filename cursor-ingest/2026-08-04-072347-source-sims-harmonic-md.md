# source / sims-harmonic.md

#doc #md

> path: source/sims-harmonic.md  
> ext: .md  

---

# sims/harmonic

#code #module #sims #math

> source_path: sims/harmonic.py  
> package: sims  
> module: sims/harmonic  
> hub: MATH  
> created_ts:   

---

**Package:** `sims`  
**Module:** `sims/harmonic`  
**Source:** `sims/harmonic.py`

Harmonically sharded index with local propagation.

Architecture
------------
The index is a ring of N shards.  Each shard i is centred on the i-th
harmonic of the fundamental attractor α = 1.96:

    basin_centre(i) = (i + 1) · α

Shards hold a scalar *activation*.  Local propagation uses a
discrete-wave / diffusion update:

    a_i(t+1) = a_i(t) + κ · [ a_{i-1}(t) + a_{i+1}(t) − 2·a_i(t) ]

where κ ∈ (0, 0.5) is the coupling constant (stability condition: κ < 0.5).

Trajectories from sims.attractors are injected by mapping their final
position to the nearest basin centre, accumulating activation in the
corresponding shard.

## API

- `class HarmonicShard` — One unit of the harmonically-indexed ring.
- `class LocalPropagator` — Nearest-neighbour diffusion propagator on a ring of shards.
- `class ResonancePropagator` — Exponential cosine resonance-sharing propagator on a ring of shards.
- `class HarmonicIndex` — Harmonically sharded index.
- `class IsometricCosinePropagator` — True isometric cosine-modulated propagator.
- `class TicketRecord` — One passage event recorded as a propagation wave crosses a hub.
- `class TicketClipper` — Station-hub passage recorder.
- `def cosine_path_count` — Number of distinct k-step routing paths on an n-shard ring under the

## Internal imports

`sims.attractors`

---

## Semantic links

→ [[harmonic-index]]
→ [[harmonic-index]]
→ [[attractors]]
→ [[sims]]
→ [[attractors]]

## Related notes

→ [[source/mcp-server-tools-harmonic]]
→ [[source/sims-temporal]]
→ [[source/engine-bridge-factory]]
→ [[source/sims-attractors]]
→ [[source/mcp-server-tools-sims]]

— import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[mcp-server-tools-harmonic]]

---

## Semantic links

→ [[sims-harmonic]]
→ [[harmonic-index]]
→ [[harmonic-index]]
→ [[mcp-server-tools-harmonic]]
→ [[sims-temporal]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-sims-harmonic-py]]
→ [[cursor-ingest/2026-08-04-072347-harmonic-index-md]]
→ [[cursor-ingest/2026-08-04-072347-phi-engine-hub-ring-py]]
→ [[cursor-ingest/2026-08-04-072347-source-sims-temporal-md]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-harmonic-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
