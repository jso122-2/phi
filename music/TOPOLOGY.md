---
hub: TOPOLOGY
shard: 5
basin: 11.76
tags: [hub, music, topology]
---

# TOPOLOGY

#hub

Hub shard 5 — graph health χ, β₁, and vault connectivity.

Injected by `inject_topology(invariant)`:

    signal = min(1.0, |χ| / (V + 1))

A more complex vault (larger absolute Euler characteristic χ) produces
a stronger TOPOLOGY signal, which propagates inward toward VAULT (shard 6)
and outward toward ARTIST (shard 4).

Also controls the ring coupling κ via `modulate_kappa(invariant)`:

    κ_eff = min(κ_base × (1 + β₁ / V), 0.45)

## Spoke context

Notes linked here describe the vault's structural state: node counts,
edge types, orphan analysis, graph health reports, β₁ evolution over time.
Link `[[graph]]` and `[[harmonic-index]]` here.

## Links

- [[graph]] — vault graph structure
- [[harmonic-index]] — the harmonic ring that this hub lives on
- [[VAULT]] — topology drives retrieval confidence
- [[psspps]] — retrieval pipeline health

## Physics

Basin centre 11.76 = 6·α. Under isometric propagation, TOPOLOGY has
neutral coupling to MOOD (shard 2) — distance d = 3/4 gives
cos(3π/4) ≈ −0.707, a mild inhibitory link that prevents topology
concerns from drowning out the emotional context layer.
