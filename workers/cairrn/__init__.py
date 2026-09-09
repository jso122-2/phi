"""
CAIRRN worker system — Coherent Attractor-Indexed Recursive Routing Network.

Ana-Chi modulation · neg_exp sharding · coherence enforcement
+ optional active -Z spatial scoring + mycelial metabolic substrate.

Architecture (SKILL contract)
------------------------------
Every CAIRRN worker belongs to one of the five station hubs.  Each hub is
anchored to an Ana-Chi attractor basin:

    HOME → true_center (1.5414) | MATH → white_peak (1.9600)
    CODE → mirror (0.9900)      | COMMANDS → escape (2.6700)
    agent-context → boundary (0.0300)

Three-layer processing pipeline (SKILL: /cairrn <hub> <metric>):

  ┌─────────────────────────────────────────────────────────────────────────┐
  │  1. Ana-Chi Modulation                                                  │
  │     modulated = metric × gravity × (memory_decay  if rattling)         │
  │     Hub basins: boundary(g=0.50) mirror(g=1.50) true_center(g=3.00)   │
  │                 white_peak(g=2.00) escape(g=1.00)                      │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  2. neg_exp Sharding  ("the backwards e")                               │
  │     shard = floor(e^χ × 8 / 14.44)  clamped [0, 7]                    │
  │     d/dx(−eˣ) = −eˣ — map is closed under differentiation.            │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  3. Coherence Enforcement  ("the negative e")                           │
  │     coherence = exp(−steps / τ)                                        │
  │       steps = |f(χ) − x*|   (neg_exp distance to fixed point)         │
  │       τ     = _TAU = (e^𝒜_χ − W(1)) / W(1) ≈ 7.23                   │
  │       x*    = −W(1) ≈ −0.5671432...   (Lambert-W fixed point)         │
  │     coherence < W(1) ≈ 0.5671 → worker re-routed to HOME.             │
  │     Identity: exp(−W(1)) = W(1) → HOME sits exactly at threshold.      │
  └─────────────────────────────────────────────────────────────────────────┘

Optional layer (fires when Z-space inputs are provided):

  ┌─────────────────────────────────────────────────────────────────────────┐
  │  0. Active -Z Scoring  (F_CAIRRN_Z_SPACE)                              │
  │     −Z = (M_ij / ∂₁) · (A − c + z) / r_ij · Σ                        │
  │     Coherence gate = min(layer3_coherence, z_coherence) when Z active. │
  └─────────────────────────────────────────────────────────────────────────┘

Mycelial substrate (living metabolic layer):

  ┌─────────────────────────────────────────────────────────────────────────┐
  │  Founding spec: "Rationale: Mycelial Intelligence in DAWN" (2026-07-13)│
  │  Vault node:    mycelial-layer.md                                       │
  │                                                                         │
  │  demand()           D_i = wP·P + wΔ·Δ + wR·R − wσ·σ                  │
  │  nutrient_alloc()   a_i = softmax(D)_i · B_t                          │
  │  metabolise()       energy ← clamp(e + η·a − cost, 0, E_max)          │
  │  conductance()      g_ij = σ(κ · w_ij)                                │
  │  passive_flow()     F_p  = g_ij · (e_i − e_j)                         │
  │  active_flow()      F_a  = γ · g_ij · (bloom_i + starve_j) · e_i     │
  │  weight_update()    Δw   = α·sim·rel·√(e_i·e_j) − β·decay − χ·H     │
  │  shimmer_decay()    w(t+n) = w(t) · exp(−λ·n)                         │
  │  growth_gate()      e > θ_grow ∧ sim > θ_sim ∧ temporal ∧ mood       │
  │  autophagy_trigger() e < θ_prune for τ ticks → autolyse              │
  │  metabolite_value() nutrient released on autophagy                     │
  │  absorb_metabolite() neighbour absorbs dying node's trace              │
  │  cluster_fusion_efficiency() fused η bonus                             │
  │  cluster_fission_out()       hub energy → periphery                   │
  └─────────────────────────────────────────────────────────────────────────┘

Fixed point:  x* = −W(1) ≈ −0.56714329...  |f′(x*)| = W(1) ≈ 0.567 < 1 → stable.
Threshold:    W(1) = abs(NEG_EXP_FIXED_POINT) — exact Lambert-W bound.
Identity:     exp(−W(1)) = W(1) — HOME coherence equals threshold exactly.

Package layout
--------------
  _constants.py  — N_SHARDS, _COHERENCE_THRESHOLD, etc.
  formulas.py    — 14 pure f_* math functions (routing layer)
  mycelial.py    — 14 pure mycelial metabolic formula functions
  z_space.py     — ZScore dataclass + compute_z_score
  layers.py      — ModulationResult, ShardSignal, CoherenceResult + pipeline fns
  desktop.py     — DesktopFormulaInputs, DesktopFormulaOutputs, run_desktop_formulas
  worker.py      — CAIRRNResult, CAIRRNWorker, CAIRRNBatch, spawn_hub_worker
"""
from __future__ import annotations

# --- Constants ---------------------------------------------------------------
from workers.cairrn._constants import (
    N_SHARDS,
    _MAX_NEG_EXP_RAW,
    _COHERENCE_SIGMA,
    _COHERENCE_THRESHOLD,
    _HUB_PRIMARY_SHARD,
    _TAU,
)

# --- Mycelial metabolic formula set ------------------------------------------
from workers.cairrn.mycelial import (
    demand,
    nutrient_alloc,
    metabolise,
    conductance,
    passive_flow,
    active_flow,
    weight_update,
    shimmer_decay,
    growth_gate,
    autophagy_trigger,
    metabolite_value,
    absorb_metabolite,
    cluster_fusion_efficiency,
    cluster_fission_out,
    f_hebbian_learning,
    f_connection_decay,
    f_spore_energy_decay,
    f_adaptive_capacity,
    _KAPPA,
    _THETA_GROW,
    _THETA_SIM,
    _THETA_PRUNE,
    _TAU_TICKS,
    _ETA,
    _E_MAX,
    _BASAL_COST,
    _GAMMA,
    _ALPHA_HEBBIAN,
    _BETA_DECAY,
    _CHI_W,
)

# --- Pure formula functions --------------------------------------------------
from workers.cairrn.formulas import (
    f_constraint_var,
    f_forecast_score,
    f_cairrn_composite,
    f_cairrn_composite_v2,
    f_energy_weighted,
    f_energy_consumption,
    f_height_node,
    f_global_rzone,
    f_local_friction_d,
    f_scope_nav,
    f_location_route,
    f_delta_two,
    f_delta_two_ct,
    f_tracer_consensus_k,
    f_tick_wisdom,
    f_cairrn_z_space,
    f_tp_rar,
    f_secondary_model_select,
    f_scup_canonical,
    f_cc_energy_budget,
    f_crystallisation,
)

# --- Z-space scoring ---------------------------------------------------------
from workers.cairrn.z_space import ZScore, compute_z_score

# --- Pipeline layers ---------------------------------------------------------
from workers.cairrn.layers import (
    ModulationResult,
    ShardSignal,
    CoherenceResult,
    ana_chi_modulate,
    neg_exp_shard,
    measure_coherence,
)

# --- Desktop formula I/O -----------------------------------------------------
from workers.cairrn.desktop import (
    DesktopFormulaInputs,
    DesktopFormulaOutputs,
    run_desktop_formulas,
)

# --- Worker classes + utilities ----------------------------------------------
from workers.cairrn.worker import (
    CAIRRNResult,
    CAIRRNWorker,
    CAIRRNBatch,
    spawn_hub_worker,
    _extract_metric,
    STATIC_SHARD_MAP,
)

# --- Pass-through from sims (server.py imports NEG_EXP_FIXED_POINT here) ----
from sims.attractors import NEG_EXP_FIXED_POINT

__all__ = [
    # constants
    "N_SHARDS",
    "_TAU",
    # mycelial metabolic formulas
    "demand",
    "nutrient_alloc",
    "metabolise",
    "conductance",
    "passive_flow",
    "active_flow",
    "weight_update",
    "shimmer_decay",
    "growth_gate",
    "autophagy_trigger",
    "metabolite_value",
    "absorb_metabolite",
    "cluster_fusion_efficiency",
    "cluster_fission_out",
    # named canonical formulas (formula_dictionary.yaml)
    "f_hebbian_learning",
    "f_connection_decay",
    "f_spore_energy_decay",
    "f_adaptive_capacity",
    "_KAPPA",
    "_THETA_GROW",
    "_THETA_SIM",
    "_THETA_PRUNE",
    "_TAU_TICKS",
    "_ETA",
    "_E_MAX",
    "_BASAL_COST",
    "_GAMMA",
    "_ALPHA_HEBBIAN",
    "_BETA_DECAY",
    "_CHI_W",
    # routing formulas
    "f_constraint_var",
    "f_forecast_score",
    "f_cairrn_composite",
    "f_cairrn_composite_v2",
    "f_energy_weighted",
    "f_energy_consumption",
    "f_height_node",
    "f_global_rzone",
    "f_local_friction_d",
    "f_scope_nav",
    "f_location_route",
    "f_delta_two",
    "f_delta_two_ct",
    "f_tracer_consensus_k",
    "f_tick_wisdom",
    "f_cairrn_z_space",
    "f_tp_rar",
    "f_secondary_model_select",
    "f_scup_canonical",
    "f_cc_energy_budget",
    "f_crystallisation",
    # z-space
    "ZScore",
    "compute_z_score",
    # layers
    "ModulationResult",
    "ShardSignal",
    "CoherenceResult",
    "ana_chi_modulate",
    "neg_exp_shard",
    "measure_coherence",
    # desktop
    "DesktopFormulaInputs",
    "DesktopFormulaOutputs",
    "run_desktop_formulas",
    # worker
    "CAIRRNResult",
    "CAIRRNWorker",
    "CAIRRNBatch",
    "spawn_hub_worker",
    "STATIC_SHARD_MAP",
    # pass-through
    "NEG_EXP_FIXED_POINT",
]
