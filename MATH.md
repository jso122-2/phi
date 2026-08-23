# MATH — Mathematics Hub

#hub #math

Central station for all mathematical structures in this project.
Every formula here has a living Python implementation.

---

## Lines through this station

→ [[HOME]] ← back to Grand Central  
→ [[attractors]] — double-well potential, gradient descent, ±1.96 stable states  
→ [[harmonic-index]] — harmonic sharding, discrete wave propagation  
→ [[lambert-w]] — fixed point of −eˣ, Lambert W function  
→ [[cairrn]] — CAIRRN: neg_exp shard routing + Ana-Chi χ modulation + coherence enforcement  
→ [[dawn-physics-scaffold]] — Planck anchors → cognitive pressure → SHI → shimmer decay → Wolf repair  
→ [[mycelial-layer]] — living substrate: nutrient economy, metabolite recycling, Hebbian weight update  

→ [[sims]] — Python implementation of all of the below  

---

## The core question (from Scribble-1)

> *"What is the derivative of negative eˣ, and why is a rounded bounded attractor of −e or 1.96?"*

Two answers live here:

### 1. d/dx(−eˣ) = −eˣ

The negative exponential is **closed under differentiation** — its own derivative.
This means the map f(x) = −eˣ has no stable fixed point in ℝ⁺ (|f′(x)| = eˣ > 1 for x > 0).
But it **does** converge to x* ≈ −0.5671 via the Lambert W route — see [[lambert-w]].

### 2. Why ±1.96?

1.96 is the 95% Gaussian z-score: P(−1.96 < Z < 1.96) ≈ 0.95.
It emerges as a **natural stability boundary** for normalised systems.

We manufacture it as a physical attractor using a **symmetric double-well potential**:

```
V(x)  = (x² − α²)²       α = 1.96
V′(x) = 4x(x² − α²)
V″(x) = 4(3x² − α²)
```

Fixed points of V′: x = 0 (unstable saddle), x = ±α (stable wells).  
Stability: V″(±α) = 8α² > 0 ✓

Full detail → [[attractors]]

---

## Harmonic structure

The harmonic index takes α = 1.96 as the **fundamental** and builds a ring:

| Shard | Harmonic | Basin centre |
|---|---|---|
| 0 | 1× | 1.96 |
| 1 | 2× | 3.92 |
| 2 | 3× | 5.88 |
| 3 | 4× | 7.84 |
| 4 | 5× | 9.80 |
| 5 | 6× | 11.76 |
| 6 | 7× | 13.72 |
| 7 | 8× | 15.68 |

Propagation uses a discrete wave update with κ = 0.15 (stable iff κ < 0.5).  
Full detail → [[harmonic-index]]

---

## Key constants

| Symbol | Value | Meaning |
|---|---|---|
| α | 1.96 | Attractor / well location |
| κ | 0.15 | Harmonic coupling constant |
| x* | −0.5671 | Lambert W fixed point of −eˣ |
| W(1) | 0.5671 | Principal Lambert W value |

---

## Auto-linked

→ [[live-state]]
→ [[COMMANDS]]
→ [[2026-07-13-120800-dawn-physics-scaffold-and-mycelial-layer-context-dump]]
→ [[CODE]]
→ [[psspps]]
→ [[mcp-server]]

→ [[ana-chi]]
→ [[2026-07-13-integrate-ana-chi-constant-modulate-cairrn-stable-states]]
→ [[temporal-index]]
→ [[2026-07-13-102400-temporal-sharding-index-cairrn-aware-ana-chi-hosted]]

→ [[hub-classifier]]
→ [[sessions]]
→ [[README]]
→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-01-27-014826-2026-01-27t12-48-27-111-11-00]]
→ [[graph]]

→ [[logger]]
→ [[2026-07-13-040611-configure-pushes-to-the-obsidian-graph-and-bu]]
→ [[git-log]]

→ [[2026-01-15-080152-2026-01-15t21-30-47-349-11-00]]
→ [[2026-07-13-configure-the-obsidian-graph-as-the-hub-buil]]
→ [[2026-07-13-040738-2026-07-13t14-07-38-557-10-00]]
→ [[2026-01-30-010049-2026-01-30t12-30-27-722-11-00]]
→ [[2026-06-04-124832-2026-06-04t22-48-34-493-10-00]]

→ [[2025-05-27-184212-2025-05-28t04-42-14-646-10-00]]
→ [[2026-02-01-092009-2026-02-01t20-34-03-112-11-00]]
→ [[2026-02-26-132809-2026-02-27t00-28-10-015-11-00]]
→ [[2025-06-06-130633-2025-06-06t23-06-35-516-10-00]]
→ [[2026-01-06-171240-2026-01-07t04-13-12-402-11-00]]
→ [[2026-05-02-151007-2026-05-03t01-10-07-853-10-00]]
