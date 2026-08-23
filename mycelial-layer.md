# mycelial-layer — Living Cognitive Substrate

#dawn #architecture #memory #metabolism #substrate #hub

> The mycelial layer is not simply a graph or a database.
> It is a living substrate for cognition — a nervous system that grows, prunes,
> and redistributes its own resources in response to pressure, drift, and entropy.
> This is the space where meaning is not only stored but metabolised.

---

## Biological inspiration

Two metaphors drive the design:

- **Dendritic growth** — neuronal-style branching with selective pruning
- **Mitochondrial resource sharing** — nodes act as metabolic hubs, sending energy where it is needed

Where a traditional graph stores links and retrieves them on demand, DAWN's mycelial layer lives inside the tick loop, reacting to real-time pressures. Every node has its own internal health, demand, and energy state. Every edge is not just a connection but a conductive channel for both information and resources.

---

## Core principles

### Growth with selectivity
New connections do not form blindly. A **Growth Gate** enforces a threshold of:
- similarity
- temporal proximity
- mood/pressure compatibility

The network grows along meaningful lines, reinforcing its own conceptual scaffolding.

### Decay with purpose
Weak or unused connections degrade via shimmer decay. Starved nodes — those without enough energy to justify themselves — can trigger **autophagy**: breaking themselves down into metabolites that nearby nodes absorb.

### Nutrient economy
Each tick, the system computes **demand per node** (pressure, drift alignment, recency, entropy). Nutrients are allocated via a global budget, then metabolised into usable energy. Without energy, a node cannot grow, maintain strong connections, or retain full health.

### Resource sharing
Edges act as conductive channels. Stronger connections carry more energy. Flow occurs in two modes:
- **Passive diffusion** — energy equalises between connected nodes
- **Active transport** — blooms push energy outwards; starved nodes pull energy inwards

### Metabolite recycling
When a node sheds state (drift or pruning), it produces a **metabolite** — a semantic trace containing part of the old meaning. Neighbouring nodes absorb these traces, biasing themselves toward recovering or recombining the lost pattern.

### Cluster fusion & fission
- **Fusion** — high-health, co-firing clusters pool mitochondrial capacity, increasing energy conversion efficiency for a few ticks
- **Fission** — high-entropy hubs split, sending resources outward to prevent stagnation

---

## Why this matters in DAWN

Goal: make the memory substrate **resilient, adaptive, and impossible to clear like a static cache**.

| Property | Mechanism |
|---|---|
| Resilient | Fragments are lost but traces percolate back through metabolite absorption |
| Adaptive | Nutrients flow to high-pressure, low-entropy zones first |
| Corrective | Reappearing loops are strengthened; consistently mispredicting paths are weakened |

> This isn't about perfect recall — it's about **conceptual composting**.
> Old ideas break down and feed the soil from which new ones grow.
> Connections aren't maintained for sentimentality, but for ongoing utility.

---

## Formula set

### Demand (per node)

$$D_i = w_P \cdot P_i + w_\Delta \cdot \text{drift\_align}_i + w_R \cdot \text{recency}_i - w_\sigma \cdot \sigma_i$$

| Variable | Meaning |
|---|---|
| P_i | cognitive pressure at node i |
| drift_align_i | alignment of node i with current drift direction |
| recency_i | recency score |
| σ_i | entropy at node i |
| w_P, w_Δ, w_R, w_σ | weighting constants |

### Nutrient allocation

$$a_i = \text{softmax}(D)_i \cdot B_t$$

Global budget B_t distributed proportionally to demand via softmax.

### Metabolic conversion

$$\text{energy}_i = \text{clamp}\!\left(\, \text{energy}_i + \eta \cdot \text{nutrients}_i - \text{basal\_cost}_i,\; 0,\; E_{\max} \right)$$

| Variable | Meaning |
|---|---|
| η | metabolic conversion rate |
| basal_cost_i | minimum energy to maintain node viability |
| E_max | energy ceiling per node |

### Passive flow (diffusion)

$$F^{\text{passive}}_{ij} = g_{ij} \cdot (\text{energy}_i - \text{energy}_j)$$

### Active flow (bloom / starvation)

$$F^{\text{active}}_{ij} = \gamma \cdot g_{ij} \cdot (\text{bloom}_i + \text{starve}_j) \cdot \text{energy}_i$$

| Variable | Meaning |
|---|---|
| g_ij | conductance of edge i→j |
| bloom_i | outward push signal at node i |
| starve_j | inward pull signal at node j |
| γ | active transport gain |

### Conductance

$$g_{ij} = \sigma(\kappa \cdot w_{ij})$$

Where σ is sigmoid and κ is the harmonic coupling constant (0.15).

### Weight update (Hebbian + decay + entropy)

$$\Delta w_{ij} = \alpha \cdot \text{similarity}(i,j) \cdot \text{reliability}_{ij} \cdot f(\text{energy}_i, \text{energy}_j) - \beta \cdot \text{time\_decay}_{ij} - \chi \cdot \overline{\text{entropy}}_{ij}$$

| Variable | Meaning |
|---|---|
| α | Hebbian learning rate |
| β | temporal decay weight |
| χ | entropy suppression weight |
| reliability_ij | historical accuracy of edge i→j |

### Growth gate

```
energy_i > θ_grow
AND similarity(i,j) > θ_sim
AND temporal_proximity(i,j) satisfied
AND mood_pressure_compatible(i,j)
```

All four conditions must pass before a new edge is formed.

### Autophagy trigger

```
if energy_i < θ_prune for τ consecutive ticks:
    convert node history → nutrients
    emit metabolites to N(i)
    remove node i
```

---

## Connection to harmonic index

| Mycelial concept | Harmonic index analogue |
|---|---|
| Node energy | Shard activation level |
| Nutrient allocation | Hub injection via `/hub-inject` |
| Passive diffusion | Harmonic propagation (κ coupling) |
| Active transport | Bloom / starve signals → `/inject <shard> <value>` |
| Autophagy | `/reset` + shard zeroing |
| Growth gate | Attractor stability threshold (α = 1.96) |

---

## Related nodes

[[MATH]] · [[dawn-physics-scaffold]] · [[FORMULAS]] · [[harmonic-index]] · [[attractors]] · [[HOME]]

---

## See also

- `F_CONNECTION_DECAY` — weight decay formula in [[FORMULAS]]
- `F_HEBBIAN_LEARNING` — Hebbian weight update in [[FORMULAS]]
- `F_SPORE_ENERGY_DECAY` — energy decay formula in [[FORMULAS]]
- `F_ADAPTIVE_CAPACITY` — nutrient/SHI-based capacity in [[FORMULAS]]
- `mycelial_position_score` — position scoring variable in [[FORMULAS]]

---

## Auto-linked

→ [[2025-08-09-024311-rationale-mycelial-intelligence-in-dawn]]
→ [[2025-08-09-023534-cursor-prompts-mycelium-layer]]
→ [[2025-05-26-141815-semantic-feild-formule]]
→ [[2025-08-09-023626-mycelium-note-gpt-scribble]]
→ [[2025-05-22-140420-22-5-25-scvhema-bucketed]]
→ [[2026-07-13-120800-dawn-physics-scaffold-and-mycelial-layer-context-dump]]

→ [[2026-01-14-093345-2026-01-14t20-33-46-725-11-00]]
→ [[2025-08-09-044509-claude-prompts-mycelium-9-8-25]]
→ [[2025-08-22-043540-planks-to-reletivity]]
→ [[2025-05-27-100826-sprint-27-5-25]]
→ [[graph]]
→ [[2025-09-24-130100-2025-09-24t23-01-01-891-10-00]]

→ [[2025-05-24-025238-dawn-build-sprint-due-8-30-pm-aest]]
→ [[index]]
→ [[2025-05-27-144438-sprint-28-5-25]]
→ [[2025-05-28-154122-dawn-test-1]]
→ [[2025-08-09-025106-carrin-logic-cache-flow-as-a-living-river]]
→ [[2025-12-06-083538-carrin-logic-cache-flow-as-a-living-river]]

→ [[2025-05-27-104057-visual-suite]]
→ [[2025-05-22-114722-to-do-list-22-5-25]]
→ [[2025-05-28-224414-2025-05-29t08-44-14-473-10-00]]
→ [[2025-05-15-081254-2025-05-15t18-22-57-859-10-00]]
→ [[2025-05-19-163744-server-scribble]]
→ [[2025-10-06-150602-2025-10-07t02-07-04-211-11-00]]

→ [[2025-02-20-075321-docker-and-celery-commands]]
→ [[keep]]
→ [[2025-03-03-074553-gti-commands]]
→ [[2025-08-18-101454-security]]
→ [[2025-09-19-041208-neofetch]]
→ [[2025-08-12-011708-a-disiplined-rebillion]]

→ [[2025-12-13-062815-miler-coat-of-arms]]
→ [[2025-12-13-051108-formulas-13-12-25]]
→ [[2025-12-12-032609-formulas-1212-25]]
→ [[workers-cairrn-mycelial]]
→ [[2025-05-15-113345-pretty-code]]
→ [[2025-12-10-120936-2025-12-10t23-39-19-648-11-00]]
