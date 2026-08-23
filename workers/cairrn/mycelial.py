"""
CAIRRN Mycelial Formula Set — pure math, no state.

Implements the full metabolic substrate formula set from:
    "Rationale: Mycelial Intelligence in DAWN"
    (Keep note, 2026-07-13 → keep/2025-08-09-024311-*.md → mycelial-layer.md)

The mycelial layer treats the CAIRRN node graph as a living metabolic
substrate.  Every node carries an energy state; every edge is a conductive
channel.  Each tick the system computes demand, allocates nutrients, converts
them to energy, diffuses and transports resources, updates edge weights, and
applies growth/decay mechanics.

All functions here are **pure** — they operate on float scalars or lists and
return floats or lists.  No node state, no class instances, no side effects.
State lives in the calling substrate (tick engine, CAIRRNDispatcher, etc.).

Formula source: mycelial-layer.md — the canonical vault node for this spec.
"""
from __future__ import annotations

import math
from typing import List


# ---------------------------------------------------------------------------
# Metabolic constants
# κ — harmonic coupling constant, shared with the harmonic index (0.15)
# ---------------------------------------------------------------------------

_KAPPA: float = 0.15
"""
κ — harmonic coupling constant.

Shared with the harmonic ring (propagation coupling).  Used here as the
sigmoid gain in conductance:  g_ij = σ(κ · w_ij).
mycelial-layer.md: "κ is the harmonic coupling constant (0.15)."
"""

_THETA_GROW: float = 0.30
"""θ_grow — minimum energy for a node to open the Growth Gate."""

_THETA_SIM: float = 0.25
"""θ_sim — minimum semantic similarity for a new edge to form."""

_THETA_PRUNE: float = 0.10
"""θ_prune — energy floor; sustained starvation below this triggers autophagy."""

_TAU_TICKS: int = 3
"""τ_ticks — consecutive ticks a node must stay starved before autophagy fires."""

_ETA: float = 0.80
"""η — metabolic conversion rate (nutrients → usable energy)."""

_E_MAX: float = 1.00
"""E_max — energy ceiling per node."""

_BASAL_COST: float = 0.02
"""Default basal metabolic cost subtracted every tick."""

_GAMMA: float = 0.50
"""γ — active transport gain (bloom/starve flows)."""

_ALPHA_HEBBIAN: float = 0.10
"""α — Hebbian learning rate for edge weight growth."""

_BETA_DECAY: float = 0.05
"""β — temporal decay weight on edge w_ij."""

_CHI_W: float = 0.03
"""χ — entropy suppression weight on edge w_ij."""

_ABSORPTION_RATE: float = 0.20
"""Rate at which a node absorbs a neighbouring metabolite into its energy."""

_FUSION_BONUS: float = 0.15
"""Per-node efficiency bonus during cluster fusion."""

_FISSION_RATE: float = 0.25
"""Fraction of hub energy distributed outward during cluster fission."""


# ---------------------------------------------------------------------------
# 1. Demand (per node)
# D_i = wP·P_i + wΔ·drift_align_i + wR·recency_i − wσ·σ_i
# ---------------------------------------------------------------------------

def demand(
    pressure: float,
    drift_align: float,
    recency: float,
    entropy: float,
    w_pressure: float = 0.40,
    w_drift: float = 0.25,
    w_recency: float = 0.20,
    w_entropy: float = 0.15,
) -> float:
    """
    Compute the metabolic demand score for a single node.

    D_i = w_P·P_i + w_Δ·drift_align_i + w_R·recency_i − w_σ·σ_i

    Parameters
    ----------
    pressure    : P_i   — cognitive pressure at node i (float, typically ≥ 0)
    drift_align : Δ_i   — alignment with current drift direction ∈ [−1, 1]
    recency     : R_i   — recency score ∈ [0, 1]
    entropy     : σ_i   — entropy at node i (higher → less desired)
    w_pressure  : w_P   — weight on pressure component  (default 0.40)
    w_drift     : w_Δ   — weight on drift alignment     (default 0.25)
    w_recency   : w_R   — weight on recency             (default 0.20)
    w_entropy   : w_σ   — weight on entropy penalty     (default 0.15)

    Returns
    -------
    float  D_i — demand score (higher → node gets more nutrients)
    """
    return (
        w_pressure * pressure
        + w_drift * drift_align
        + w_recency * recency
        - w_entropy * entropy
    )


# ---------------------------------------------------------------------------
# 2. Nutrient allocation (softmax budget distribution)
# a_i = softmax(D)_i · B_t
# ---------------------------------------------------------------------------

def nutrient_alloc(demands: List[float], budget: float) -> List[float]:
    """
    Distribute a global nutrient budget proportionally to node demand.

    a_i = softmax(D)_i · B_t

    Numerically stable softmax: subtract max(D) before exponentiation.

    Parameters
    ----------
    demands : List[float]  — D_i scores for each node (any real values)
    budget  : B_t          — total nutrient budget this tick (≥ 0)

    Returns
    -------
    List[float]  — nutrient allocation per node; sums to budget.
                   Empty list when demands is empty.
    """
    if not demands:
        return []
    max_d = max(demands)
    exps = [math.exp(d - max_d) for d in demands]
    total = sum(exps)
    return [(e / total) * budget for e in exps]


# ---------------------------------------------------------------------------
# 3. Metabolic conversion
# energy_i = clamp(energy_i + η·nutrients_i − basal_cost_i, 0, E_max)
# ---------------------------------------------------------------------------

def metabolise(
    energy: float,
    nutrients: float,
    basal_cost: float = _BASAL_COST,
    eta: float = _ETA,
    e_max: float = _E_MAX,
) -> float:
    """
    Convert incoming nutrients into node energy, subtract basal cost, clamp.

    energy_i ← clamp( energy_i + η·nutrients_i − basal_cost_i , 0, E_max )

    Parameters
    ----------
    energy     : current energy level of node i     ∈ [0, E_max]
    nutrients  : nutrients_i allocated this tick     (≥ 0)
    basal_cost : minimum energy cost per tick        (default _BASAL_COST)
    eta        : η — metabolic conversion rate       (default _ETA)
    e_max      : E_max — energy ceiling              (default _E_MAX)

    Returns
    -------
    float  — updated energy after metabolic conversion, clamped to [0, E_max]
    """
    updated = energy + eta * nutrients - basal_cost
    return max(0.0, min(e_max, updated))


# ---------------------------------------------------------------------------
# 4. Conductance
# g_ij = σ(κ · w_ij)   where σ is sigmoid, κ is the harmonic coupling const
# ---------------------------------------------------------------------------

def conductance(weight: float, kappa: float = _KAPPA) -> float:
    """
    Compute edge conductance from edge weight via sigmoid.

    g_ij = σ(κ · w_ij) = 1 / (1 + exp(−κ · w_ij))

    Stronger, more reliable connections carry more energy.
    κ = 0.15 is the harmonic coupling constant shared with the harmonic ring.

    Parameters
    ----------
    weight : w_ij — edge weight (any real; positive = established connection)
    kappa  : κ    — sigmoid gain (default _KAPPA = 0.15)

    Returns
    -------
    float  g_ij ∈ (0, 1)
    """
    return 1.0 / (1.0 + math.exp(-kappa * weight))


# ---------------------------------------------------------------------------
# 5. Passive flow (diffusion)
# F_passive_ij = g_ij · (energy_i − energy_j)
# ---------------------------------------------------------------------------

def passive_flow(energy_i: float, energy_j: float, weight_ij: float) -> float:
    """
    Energy diffusion from node i to node j along edge ij.

    F_passive_ij = g_ij · (energy_i − energy_j)

    Positive → energy flows i→j.
    Negative → energy flows j→i.
    Magnitude scales with conductance and energy differential.

    Parameters
    ----------
    energy_i  : energy at source node i
    energy_j  : energy at destination node j
    weight_ij : edge weight w_ij (used to compute g_ij)

    Returns
    -------
    float  — signed flow; add to j, subtract from i.
    """
    g = conductance(weight_ij)
    return g * (energy_i - energy_j)


# ---------------------------------------------------------------------------
# 6. Active flow (bloom / starvation)
# F_active_ij = γ · g_ij · (bloom_i + starve_j) · energy_i
# ---------------------------------------------------------------------------

def active_flow(
    energy_i: float,
    bloom_i: float,
    starve_j: float,
    weight_ij: float,
    gamma: float = _GAMMA,
) -> float:
    """
    Active transport: blooms push energy outward; starved nodes pull it in.

    F_active_ij = γ · g_ij · (bloom_i + starve_j) · energy_i

    bloom_i  — outward push signal at node i (0 when quiescent, > 0 when blooming)
    starve_j — inward pull signal at node j  (0 when healthy, > 0 when starving)

    Parameters
    ----------
    energy_i  : energy at source node i
    bloom_i   : bloom signal at node i  (≥ 0)
    starve_j  : starvation signal at j  (≥ 0)
    weight_ij : edge weight w_ij
    gamma     : γ — active transport gain (default _GAMMA = 0.50)

    Returns
    -------
    float  — active flow from i to j (≥ 0)
    """
    g = conductance(weight_ij)
    return gamma * g * (bloom_i + starve_j) * energy_i


# ---------------------------------------------------------------------------
# 7. Weight update (Hebbian + temporal decay + entropy suppression)
# Δw_ij = α·sim·reliability·f(e_i,e_j) − β·time_decay − χ·mean_entropy
# ---------------------------------------------------------------------------

def weight_update(
    similarity_ij: float,
    reliability_ij: float,
    energy_i: float,
    energy_j: float,
    time_decay_ij: float,
    mean_entropy_ij: float,
    alpha: float = _ALPHA_HEBBIAN,
    beta: float = _BETA_DECAY,
    chi_w: float = _CHI_W,
) -> float:
    """
    Compute the weight delta for edge ij over one tick.

    Δw_ij = α · similarity(i,j) · reliability_ij · f(energy_i, energy_j)
            − β · time_decay_ij
            − χ · mean_entropy_ij

    f(energy_i, energy_j) = geometric mean √(energy_i · energy_j).
    Both nodes must be energetically active for Hebbian growth to occur.

    Parameters
    ----------
    similarity_ij   : semantic similarity of nodes i and j  ∈ [0, 1]
    reliability_ij  : historical accuracy / consistency of edge ij ∈ [0, 1]
    energy_i        : energy at node i
    energy_j        : energy at node j
    time_decay_ij   : time elapsed since last activation (non-negative)
    mean_entropy_ij : mean entropy on edge ij
    alpha           : α — Hebbian learning rate   (default _ALPHA_HEBBIAN)
    beta            : β — temporal decay weight   (default _BETA_DECAY)
    chi_w           : χ — entropy suppression     (default _CHI_W)

    Returns
    -------
    float  Δw_ij — signed delta; add to current weight to get w_ij(t+1)
    """
    mutual_energy = math.sqrt(max(0.0, energy_i) * max(0.0, energy_j))
    hebbian = alpha * similarity_ij * reliability_ij * mutual_energy
    decay   = beta * time_decay_ij
    entropy = chi_w * mean_entropy_ij
    return hebbian - decay - entropy


# ---------------------------------------------------------------------------
# 8. Shimmer decay (passive weight degradation over unused time)
# w_ij(t+n) = w_ij(t) · exp(−decay_rate · n)
# ---------------------------------------------------------------------------

def shimmer_decay(weight: float, time_steps: float, decay_rate: float = 0.02) -> float:
    """
    Exponential decay of an edge weight over unused time.

    w_ij(t+n) = w_ij(t) · exp(−decay_rate · n)

    Weak or unused connections degrade over time via shimmer decay.
    Apply this to edges that have not carried flow recently.

    Parameters
    ----------
    weight     : w_ij — current edge weight
    time_steps : n    — ticks since last activation (≥ 0)
    decay_rate : λ    — shimmer decay rate per tick (default 0.02)

    Returns
    -------
    float  — decayed edge weight (same sign as input, magnitude ≤ |weight|)
    """
    return weight * math.exp(-decay_rate * max(0.0, time_steps))


# ---------------------------------------------------------------------------
# 9. Growth gate (4-condition check)
# energy_i > θ_grow AND similarity > θ_sim AND temporal_ok AND mood_ok
# ---------------------------------------------------------------------------

def growth_gate(
    energy_i: float,
    similarity_ij: float,
    temporal_ok: bool,
    mood_ok: bool,
    theta_grow: float = _THETA_GROW,
    theta_sim: float = _THETA_SIM,
) -> bool:
    """
    Check all four Growth Gate conditions before forming a new edge.

    energy_i > θ_grow           — node must be energetically viable
    AND similarity(i,j) > θ_sim — connection must be semantically justified
    AND temporal_proximity ok   — nodes must be temporally proximate
    AND mood/pressure compatible — system state must be compatible

    All four conditions must pass.  Returns False if any fails.

    Parameters
    ----------
    energy_i      : energy at source node i
    similarity_ij : semantic similarity of i and j ∈ [0, 1]
    temporal_ok   : True when temporal proximity condition is satisfied
    mood_ok       : True when mood/pressure compatibility is satisfied
    theta_grow    : θ_grow — minimum energy threshold (default _THETA_GROW)
    theta_sim     : θ_sim  — minimum similarity threshold (default _THETA_SIM)

    Returns
    -------
    bool  — True when all four gate conditions pass; edge may be formed.
    """
    return (
        energy_i > theta_grow
        and similarity_ij > theta_sim
        and temporal_ok
        and mood_ok
    )


# ---------------------------------------------------------------------------
# 10. Autophagy trigger
# Fires when energy_i < θ_prune for τ consecutive ticks
# ---------------------------------------------------------------------------

def autophagy_trigger(
    energy: float,
    starved_ticks: int,
    theta_prune: float = _THETA_PRUNE,
    tau_ticks: int = _TAU_TICKS,
) -> bool:
    """
    Determine whether a node should self-digest (autophagy).

    Trigger condition: energy_i < θ_prune for τ consecutive ticks.

    When triggered, the calling substrate should:
        1. convert node history → nutrients via metabolite_value()
        2. emit metabolites to each neighbour N(i) via absorb_metabolite()
        3. remove node i from the graph

    Parameters
    ----------
    energy       : current energy level of node i
    starved_ticks: consecutive ticks where energy was below θ_prune
    theta_prune  : θ_prune — starvation threshold (default _THETA_PRUNE)
    tau_ticks    : τ_ticks — ticks of sustained starvation to trigger (default _TAU_TICKS)

    Returns
    -------
    bool  — True when the node should autolyse this tick.
    """
    return energy < theta_prune and starved_ticks >= tau_ticks


# ---------------------------------------------------------------------------
# 11. Metabolite value (energy released when a node autophagises)
# ---------------------------------------------------------------------------

def metabolite_value(
    energy: float,
    history_factor: float = 1.0,
    nutrient_factor: float = 0.60,
) -> float:
    """
    Compute the nutrient value of the metabolite emitted by an autolysing node.

    metabolite = (energy + history_factor) · nutrient_factor

    The metabolite carries both residual energy and a fraction of the node's
    accumulated history.  Neighbouring nodes absorb this via absorb_metabolite().

    Parameters
    ----------
    energy         : residual energy of the dying node (≥ 0)
    history_factor : semantic trace weight from node history (≥ 0, default 1.0)
    nutrient_factor: fraction converted to usable metabolite (default 0.60)

    Returns
    -------
    float  — metabolite nutrient value (≥ 0)
    """
    return (energy + history_factor) * nutrient_factor


# ---------------------------------------------------------------------------
# 12. Metabolite absorption (neighbour absorbs a dying node's trace)
# ---------------------------------------------------------------------------

def absorb_metabolite(
    energy: float,
    metabolite: float,
    absorption_rate: float = _ABSORPTION_RATE,
    e_max: float = _E_MAX,
) -> float:
    """
    Add a fraction of a metabolite to a neighbour node's energy.

    energy_j ← clamp( energy_j + absorption_rate · metabolite, 0, E_max )

    Neighbouring nodes absorb semantic traces from autolysed nodes, biasing
    themselves toward recovering or recombining lost patterns.

    Parameters
    ----------
    energy         : current energy of the absorbing node j
    metabolite     : nutrient value from metabolite_value() (≥ 0)
    absorption_rate: fraction of metabolite absorbed per tick (default _ABSORPTION_RATE)
    e_max          : E_max — energy ceiling (default _E_MAX)

    Returns
    -------
    float  — updated energy of node j, clamped to [0, E_max]
    """
    return max(0.0, min(e_max, energy + absorption_rate * metabolite))


# ---------------------------------------------------------------------------
# 13. Cluster fusion — pooled mitochondrial efficiency
# ---------------------------------------------------------------------------

def cluster_fusion_efficiency(
    base_efficiency: float,
    n_nodes: int,
    fusion_bonus: float = _FUSION_BONUS,
) -> float:
    """
    Compute the energy conversion efficiency during a cluster fusion event.

    efficiency = base_efficiency + fusion_bonus · n_nodes
    Clamped to [0, 1] — efficiency cannot exceed 100 %.

    High-health co-firing clusters fuse, pooling mitochondrial capacity and
    increasing energy conversion for a few ticks.

    Parameters
    ----------
    base_efficiency : η of the cluster before fusion ∈ [0, 1]
    n_nodes         : number of nodes joining the fused cluster (≥ 1)
    fusion_bonus    : per-node efficiency bonus (default _FUSION_BONUS = 0.15)

    Returns
    -------
    float  — fused efficiency ∈ [0, 1]
    """
    return min(1.0, base_efficiency + fusion_bonus * max(1, n_nodes))


# ---------------------------------------------------------------------------
# 14. Cluster fission — hub energy pushed to periphery
# ---------------------------------------------------------------------------

def cluster_fission_out(
    energy_hub: float,
    n_periphery: int,
    fission_rate: float = _FISSION_RATE,
) -> List[float]:
    """
    Distribute a fraction of a high-entropy hub's energy to peripheral nodes.

    Each peripheral node receives:  (energy_hub · fission_rate) / n_periphery

    High-entropy hubs fission — sending resources outward to prevent stagnation.
    The hub retains energy_hub · (1 − fission_rate) after the event.

    Parameters
    ----------
    energy_hub  : current energy of the hub node (≥ 0)
    n_periphery : number of peripheral nodes to distribute to (≥ 1)
    fission_rate: fraction of hub energy pushed outward (default _FISSION_RATE)

    Returns
    -------
    List[float]  — energy delta for each peripheral node (length = n_periphery)
                   Empty list when n_periphery < 1.
    """
    if n_periphery < 1:
        return []
    share = (energy_hub * fission_rate) / n_periphery
    return [share] * n_periphery


# ---------------------------------------------------------------------------
# Named canonical formulas — from config/formulas/formula_dictionary.yaml
# Referenced in mycelial-layer.md → [[FORMULAS]]
# These use the F_ prefix convention to match the formula dictionary IDs.
# ---------------------------------------------------------------------------

def f_hebbian_learning(
    eta: float,
    a_i: float,
    a_j: float,
) -> float:
    """
    F_HEBBIAN_LEARNING — Hebbian weight update.

    Δw_ij = η · a_i · a_j

    Neurons that fire together wire together.  Stronger co-activation
    of nodes i and j increases the connection weight proportionally.

    Parameters
    ----------
    eta : η — Hebbian learning rate (> 0)
    a_i : activation level of node i  ∈ [0, 1]
    a_j : activation level of node j  ∈ [0, 1]

    Returns
    -------
    float  Δw_ij — weight delta to add to w_ij this tick
    """
    return eta * a_i * a_j


def f_connection_decay(
    strength: float,
    decay_rate: float,
) -> float:
    """
    F_CONNECTION_DECAY — Linear connection strength decay per tick.

    strength_new = strength · (1 − decay_rate)

    Weak or unused connections degrade each tick by a fixed fraction.
    Paired with shimmer_decay() (exponential) for tunable decay profiles:
    use f_connection_decay() for per-tick proportional erosion;
    use shimmer_decay() for time-elapsed exponential decay.

    Parameters
    ----------
    strength   : current connection strength w_ij (any real; typically ≥ 0)
    decay_rate : fraction removed per tick ∈ [0, 1]

    Returns
    -------
    float  — decayed connection strength
    """
    return strength * (1.0 - max(0.0, min(1.0, decay_rate)))


def f_spore_energy_decay(
    e_old: float,
    decay_rate: float,
) -> float:
    """
    F_SPORE_ENERGY_DECAY — Exponential spore energy decay.

    E_new = E_old · exp(−decay_rate)

    Models the natural dissipation of energy in dormant spore nodes —
    nodes that have been cut off from the main nutrient flow.
    More aggressive than f_connection_decay() for isolated node states.

    Parameters
    ----------
    e_old      : energy before decay  (≥ 0)
    decay_rate : exponential decay constant per tick  (≥ 0)

    Returns
    -------
    float  E_new — energy after one decay step (≥ 0)
    """
    return max(0.0, e_old * math.exp(-max(0.0, decay_rate)))


def f_adaptive_capacity(
    w_n: float,
    nutrient_headroom: float,
    w_s: float,
    shi_margin: float,
    w_t: float,
    tracer_slack: float,
    tag_set_a: float = 0.0,
) -> float:
    """
    F_ADAPTIVE_CAPACITY — Weighted adaptive capacity score.

    AC = w_N · N + w_S · M_SHI + w_T · S_T + A

    Combines three headroom signals into a single capacity score.
    High AC → system has room to grow new connections / absorb metabolites.
    Low AC  → system is at capacity; Growth Gate is more likely to block.

    Parameters
    ----------
    w_n               : w_N  — weight on nutrient headroom  (≥ 0)
    nutrient_headroom : N    — spare nutrient budget this tick  (≥ 0)
    w_s               : w_S  — weight on SHI margin  (≥ 0)
    shi_margin        : M_SHI = max(0, SHI − θ_safe)  (≥ 0)
    w_t               : w_T  — weight on tracer slack  (≥ 0)
    tracer_slack      : S_T  — spare tracer capacity  (≥ 0)
    tag_set_a         : A    — tag-set-A activation bonus  (default 0.0)

    Returns
    -------
    float  AC — adaptive capacity score (higher → more capacity)
    """
    return (
        w_n * nutrient_headroom
        + w_s * shi_margin
        + w_t * tracer_slack
        + tag_set_a
    )
