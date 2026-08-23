"""
CAIRRN routing formula functions — pure math, no state.

These are the **routing / desktop** formulas: they operate on the
Ana-Chi attractor pipeline (modulation → sharding → coherence).

⚠️  VARIABLE NAME DISAMBIGUATION
Variables like `energy`, `nutrients`, and `pressure` appear in both this
file and in `mycelial.py`, but they play different structural roles:

  formulas.py (routing layer)          mycelial.py (metabolic layer)
  ─────────────────────────────────    ──────────────────────────────
  energy     = CAIRRN routing energy   energy   = node metabolic energy
  nutrients  = SCUP nutrient term      nutrients = softmax budget share
  pressure   = SCUP pressure metric    pressure  = cognitive demand input

Do NOT use formulas from this file to implement mycelial mechanics.
The metabolic substrate formula set lives exclusively in `mycelial.py`.

Organised by pipeline layer:
  Layer X — composite / constraint (cross-layer)
  Layer 1 — Ana-Chi Modulation
  Layer 2 — neg_exp Sharding
  Layer 3 — Coherence Enforcement
  Z-Space — active -Z spatial scoring (raw formula only)
"""
from __future__ import annotations

import math
from typing import List


# ---------------------------------------------------------------------------
# Layer X — composite / constraint
# ---------------------------------------------------------------------------

def f_constraint_var(likelihood: float, possibility: float, opportunity_cost: float) -> float:
    """
    F_CONSTRAINT_VAR:  x_c = Lh / P − O

    Guards against division-by-zero: returns 1e-9 when P == 0.

    Parameters
    ----------
    likelihood      : Lh ∈ [0, 1]
    possibility     : P  ∈ [0, 1]
    opportunity_cost: O  (float)
    """
    p = possibility if possibility != 0.0 else 1e-9
    return likelihood / p - opportunity_cost


def f_forecast_score(
    forecasting_result: float,
    constraint_var: float,
    temporal_validator: float,
    energy_available: float,
) -> float:
    """
    F_FORECAST_SCORE:  score = |(D − e) / x_c| · T · Δj

    Parameters
    ----------
    forecasting_result : D  (float %, typically [0, 1])
    constraint_var     : x_c (output of f_constraint_var; guarded ≠ 0)
    temporal_validator : T
    energy_available   : Δj
    """
    xc = constraint_var if constraint_var != 0.0 else 1e-9
    return abs((forecasting_result - math.e) / xc) * temporal_validator * energy_available


def f_cairrn_composite(
    confidence: float,
    scope: float,
    dawn_data: float,
    energy_cost: float,
    tick_interval: int,
) -> float:
    """
    F_CAIRRN_COMPOSITE:  Ψ = |z+x|·|1−c| − |z+x|·|y−c| + Ti

    Parameters
    ----------
    confidence    : z  ∈ [0, 1]
    scope         : x  (SCUP coordinate)
    dawn_data     : y  (DAWN state value)
    energy_cost   : c  (metabolic cost)
    tick_interval : Ti (current tick #)
    """
    zx = abs(confidence + scope)
    return zx * abs(1.0 - energy_cost) - zx * abs(dawn_data - energy_cost) + tick_interval


def f_tp_rar(
    c_e: float,
    cl_e: float,
    lam: float,
    dt: float,
    p: float,
    conf_ma: float = 1.0,
) -> float:
    """
    F_TP_RAR:  TP_RAR_E = (C_E − (1 − cl_E)·λ − Δt·p) / TP_RAR_conf_ma

    Time-Penalised Risk Adjusted Return.  Phi ranker wraps this as tp_rar_score.
    """
    denom = conf_ma if abs(conf_ma) > 1e-12 else 1e-12
    return (c_e - (1.0 - cl_e) * lam - dt * p) / denom


def f_secondary_model_select(tp_rar_pi: float, tp_rar_optimal: float) -> float:
    """
    F_SECONDARY_MODEL_SELECT:  MS_i = 1 if TP_RAR_Pi < TP_RAR_optimal else 0
    """
    return 1.0 if tp_rar_pi < tp_rar_optimal else 0.0


# ---------------------------------------------------------------------------
# Layer 1 — Ana-Chi Modulation
# ---------------------------------------------------------------------------

def f_energy_weighted(
    energies: List[float],
    desirability_costs: List[float],
    resources: float,
    dist_weighted_times: List[float],
    positive_normalisation: float,
) -> float:
    """
    F_ENERGY_WEIGHTED:  EW = Σ(i=1..n) |x_i − z_i| / A · T_Dw_i · n_w

    Parameters
    ----------
    energies              : x_i  per-node energy values
    desirability_costs    : z_i  per-node desirability cost
    resources             : A    total resource float
    dist_weighted_times   : T_Dw distance-weighted time per node
    positive_normalisation: n_w  > 0
    """
    A   = resources if resources != 0.0 else 1e-9
    n_w = positive_normalisation if positive_normalisation != 0.0 else 1e-9
    total = sum(
        abs(x - z) / A * tdw
        for x, z, tdw in zip(energies, desirability_costs, dist_weighted_times)
    )
    return total * n_w


def f_energy_consumption(
    required_energy: float,
    current_position: float,
    temporal_validator: float,
    performance: float,
    tracer_consensus_value: float,
) -> float:
    """
    F_ENERGY_CONSUMPTION:  Ec = (|C − A| · T / p) · Tcv

    Parameters
    ----------
    required_energy        : C
    current_position       : A
    temporal_validator     : T
    performance            : p  ∈ (0, 1]
    tracer_consensus_value : Tcv
    """
    p = performance if performance != 0.0 else 1e-9
    return (abs(required_energy - current_position) * temporal_validator / p) * tracer_consensus_value


def f_height_node(
    global_friction: float,
    current_mode: float,
    tracer_consensus_value: float,
) -> float:
    """
    F_HEIGHT_NODE:  H = |g + A| − Tcv

    Parameters
    ----------
    global_friction        : g
    current_mode           : A
    tracer_consensus_value : Tcv
    """
    return abs(global_friction + current_mode) - tracer_consensus_value


def f_global_rzone(
    rzone_coordinate: float,
    pressure_gradient: float,
    tracer_consensus_value: float,
    SHI: float,
) -> float:
    """
    F_GLOBAL_RZONE:  G = |r²| / ∂β · Tcv − β

    Parameters
    ----------
    rzone_coordinate       : r
    pressure_gradient      : ∂β  (guarded ≠ 0)
    tracer_consensus_value : Tcv
    SHI                    : β   (Semantic Hash Index)
    """
    d_beta = pressure_gradient if pressure_gradient != 0.0 else 1e-9
    return abs(rzone_coordinate ** 2) / d_beta * tracer_consensus_value - SHI


def f_local_friction_d(
    local_friction: float,
    tick_weighted_sum: float,
    confidence: float,
    SCOP: float,
    pressure: float,
) -> float:
    """
    F_LOCAL_FRICTION_D:  fl = |δz − Tks| · (x / z) + β

    Parameters
    ----------
    local_friction   : δz
    tick_weighted_sum: Tks
    confidence       : x  ∈ [0, 1]
    SCOP             : z  (guarded ≠ 0)
    pressure         : β
    """
    z = SCOP if SCOP != 0.0 else 1e-9
    return abs(local_friction - tick_weighted_sum) * (confidence / z) + pressure


# ---------------------------------------------------------------------------
# Layer 2 — neg_exp Sharding
# ---------------------------------------------------------------------------

def f_scope_nav(
    current_node: float,
    current_objective: float,
    energy_to_move: float,
    boolean_temporal: int,
    SHI: float,
) -> float:
    """
    F_SCOPE_NAV:  z = ||A + J| − β| · x / √D

    Parameters
    ----------
    current_node      : A
    current_objective : J
    energy_to_move    : β
    boolean_temporal  : x  ∈ {0, 1}
    SHI               : D  (guarded > 0)
    """
    D = SHI if SHI > 0.0 else 1e-9
    return abs(abs(current_node + current_objective) - energy_to_move) * boolean_temporal / math.sqrt(D)


def f_location_route(
    location: float,
    energy_projected: float,
    ticks_to_move: int,
    distance_per_waypoint: List[float],
) -> float:
    """
    F_LOCATION_ROUTE:  R_loc = |x / F| · |T · Σ D_w|

    Parameters
    ----------
    location              : x
    energy_projected      : F  (guarded ≠ 0)
    ticks_to_move         : T
    distance_per_waypoint : D_w
    """
    F = energy_projected if energy_projected != 0.0 else 1e-9
    return abs(location / F) * abs(ticks_to_move * sum(distance_per_waypoint))


# ---------------------------------------------------------------------------
# Layer 3 — Coherence Enforcement
# ---------------------------------------------------------------------------

def f_scup_canonical(
    s_i: float,
    tp_rar: float,
    p_s: float,
    u_p: float,
) -> float:
    """
    F_SCUP_CANONICAL:  SCUP = (S_i × TP_RAR) / (1 + P_s + U_p)
    """
    return (s_i * tp_rar) / (1.0 + p_s + u_p)


def f_delta_two(
    semantic_distance: float,
    time_steps: float,
    pressure_gradient: float,
    opportunity_cost: float,
) -> float:
    """
    F_DELTA_TWO:  δ₂ = |D_n + T| / |∂p| · O / T

    Parameters
    ----------
    semantic_distance : D_n
    time_steps        : T   (guarded ≠ 0)
    pressure_gradient : ∂p  (guarded ≠ 0)
    opportunity_cost  : O
    """
    T  = time_steps if time_steps != 0.0 else 1e-9
    dp = pressure_gradient if pressure_gradient != 0.0 else 1e-9
    return abs(semantic_distance + T) / abs(dp) * opportunity_cost / T


def f_delta_two_ct(
    semantic_distance: float,
    time_steps: float,
    tick_count: int,
) -> float:
    """
    F_DELTA_TWO_CT:  g2 = |D + T| · U/T · CT     (U = 1 — pressure-free variant)

    Tick-count-weighted δ₂ from Sheet 4 (phi-routing-diagnosis-2026-08-04).

    Differences from F_DELTA_TWO:
      - Replaces pressure gradient |∂p| with Unity (U = 1) — removes pressure
        dependency so g2 does not collapse when ∂p is near zero.
      - Replaces opportunity cost O with current tick count CT — later ticks in a
        session carry more routing authority.  g2 grows linearly with CT, giving
        the harmonic ring long-run calibration without external calibration inputs.

    Use alongside F_DELTA_TWO (not as a replacement) for sessions that benefit
    from building authority over time.  Short sessions (CT < 10) will produce
    very small g2 values; long sessions (CT > 100) will dominate the signal.

    Parameters
    ----------
    semantic_distance : D    — DK semantic distance between current and prior state
    time_steps        : T    — elapsed time steps (guarded ≠ 0)
    tick_count        : CT   — current session tick index (integer ≥ 0)
    """
    T = time_steps if time_steps != 0.0 else 1e-9
    return abs(semantic_distance + T) / T * tick_count


def f_cairrn_composite_v2(
    confidence: float,
    scope: float,
    energy: float,
    global_friction: float,
    n_windows: int,
    tick_interval: float,
) -> float:
    """
    F_CAIRRN_COMPOSITE_V2:
        Ψ′ = |z+x| · |1−e|  −  Ti · Σ(n_windows) |2+x| · |g−e|  +  Ti

    Ti-windowed composite from Sheet 4 (phi-routing-diagnosis-2026-08-04).

    Differences from F_CAIRRN_COMPOSITE (Ψ):
      - energy e = energy_cost − CAIRRN_score rather than bare energy_cost.
        This feeds routing feedback back into the composite: a high CAIRRN score
        reduces the effective energy, tightening the first term.
      - Second |z+x| factor replaced by Ti · Σ |2+x| · |g−e|.
        The sum over n_windows captures sustained inference pressure (e.g. a CLAP
        batch running over multiple ticks) rather than a single-tick snapshot.
      - |y−c| replaced by |g−e|: global friction vs energy-cost gap.

    Stability: Ψ′ stays positive while Ti < Ti* (see f_composite_health_horizon).
    Use f_composite_health_horizon to find the maximum safe tick interval.

    Parameters
    ----------
    confidence    : z — SCOP z-awareness (z_awareness from DispatchResult)
    scope         : x — scope coordinate
    energy        : e — energy_cost minus current CAIRRN routing score (gap signal)
    global_friction: g — global friction scalar (LOCAL_FRICTION proxy)
    n_windows     : N — number of active tick windows in the summation (≥ 1)
    tick_interval : Ti — current tick interval index
    """
    term_a      = abs(confidence + scope) * abs(1.0 - energy)
    window_sum  = max(n_windows, 1) * abs(2.0 + scope) * abs(global_friction - energy)
    return term_a - tick_interval * window_sum + tick_interval


def f_tracer_consensus_k(tracer_consensus_value: float, SHI: float) -> float:
    """
    F_TRACER_CONSENSUS_K:  K = |Tcv| − D

    Parameters
    ----------
    tracer_consensus_value : Tcv
    SHI                    : D
    """
    return abs(tracer_consensus_value) - SHI


def f_tick_wisdom(
    tracer_at_n: float,
    tip_value: float,
    tracer_consensus_k: float,
) -> float:
    """
    F_TICK_WISDOM:  Tws = Tn / K   (only when Tn ≥ Tip)

    Returns 0.0 when Tn < Tip.  Guards against K == 0.

    Parameters
    ----------
    tracer_at_n       : Tn
    tip_value         : Tip  (threshold)
    tracer_consensus_k: K    (guarded ≠ 0)
    """
    if tracer_at_n < tip_value:
        return 0.0
    K = tracer_consensus_k if tracer_consensus_k != 0.0 else 1e-9
    return tracer_at_n / K


# ---------------------------------------------------------------------------
# Z-Space — raw spatial formula (no shard assignment here — see z_space.py)
# ---------------------------------------------------------------------------

def f_cairrn_z_space(
    semantic_matrix_value: float,
    partial_deriv_1: float,
    activation: float,
    energy_cost: float,
    uncertainty: float,
    rizomic_distance: float,
    sigma_accumulator: float,
) -> float:
    """
    F_CAIRRN_Z_SPACE:  −Z = (M_ij / ∂₁) · (A − c + z) / r_ij · Σ

    CAIRRN spatial Z coordinate (always negative by convention).

    Parameters
    ----------
    semantic_matrix_value : M_ij
    partial_deriv_1       : ∂₁     (guarded ≠ 0)
    activation            : A
    energy_cost           : c
    uncertainty           : z      (SCOP value)
    rizomic_distance      : r_ij   (guarded ≠ 0)
    sigma_accumulator     : Σ
    """
    d1  = partial_deriv_1 if partial_deriv_1 != 0.0 else 1e-9
    rij = rizomic_distance if rizomic_distance != 0.0 else 1e-9
    return (semantic_matrix_value / d1) * (activation - energy_cost + uncertainty) / rij * sigma_accumulator


# ---------------------------------------------------------------------------
# Dual energy-weighted forms + geometric mean generalisation
# ---------------------------------------------------------------------------


def f_energy_weighted_geom(
    energies: List[float],
    desirability_costs: List[float],
    A: float,
    dist_weighted_times: List[float],
    positive_normalisation: float,
    w: float = 0.5,
) -> float:
    """
    F_ENERGY_WEIGHTED_GEOM:  Z_geom = Σ |x_i − z_i| · A^(2w−1) / (T_Dw_i · n_w)

    Geometric mean generalisation bridging the two dual energy-weighted forms:

        w = 0  →  divide form (vault EW):  Σ |x−z| / A     ← buffer-capacity
        w = 0.5→  neutral form:            Σ |x−z|          ← resources drop out
        w = 1  →  multiply form (sheet Z): Σ |x−z| · A     ← market-power

    The parameter w is the "resource philosophy" — how much resources (A) amplify
    vs dampen the deviation signal.  Calibrate from observed queue behaviour:
      - Set w < 0.5 when the queue should stabilise around well-resourced shards
      - Set w > 0.5 when high-resource shards should dominate exploration

    Parameters
    ----------
    energies              : per-node energy values x_i
    desirability_costs    : per-node desirability costs z_i
    A                     : total resources (n_w weighted)
    dist_weighted_times   : distance-weighted times T_Dw_i per node
    positive_normalisation: n_w — positive normalisation scalar
    w                     : resource philosophy ∈ [0, 1]  (default 0.5 = neutral)
    """
    if not energies:
        return 0.0
    n_w = positive_normalisation if abs(positive_normalisation) > 1e-9 else 1e-9
    resource_scale = A ** (2.0 * w - 1.0)
    total = 0.0
    for x_i, z_i, t_i in zip(energies, desirability_costs, dist_weighted_times):
        t_safe = t_i if abs(t_i) > 1e-9 else 1e-9
        total += abs(x_i - z_i) * resource_scale / (t_safe * n_w)
    return total


def f_composite_health_horizon(
    z: float,
    x: float,
    e: float,
    g: float,
    n_windows: int,
    ti: float,
) -> float:
    """
    Ti* — composite health horizon: the maximum tick interval before Ψ′ goes negative.

    Derived from the tick-speed stability criterion for the Ψ′ composite:

        Ψ′ = |z+x| · |1−e|  +  Ti · (1 − Σ|2+x| · |g−e|)
           = A            +  Ti · (1 − B)

    Ψ′ stays positive while Ti < Ti*:

        Ti* = A / (B − 1)    when B > 1
            = ∞              when B ≤ 1  (tick speed is irrelevant — composite always healthy)

    where:
        A = |z+x| · |1−e|           amplitude (SCOP × energy gap)
        B = Σ|2+x| · |g−e|          summed friction-energy mismatch (lower bound = 2N·|g−e|)

    Returns
    -------
    float — Ti* in the same units as ti.  Returns math.inf when B ≤ 1.
    Returns 0.0 on degenerate inputs (A = 0 and B > 1).

    Parameters
    ----------
    z         : z_awareness (SCOP z-score)
    x         : modulated / confidence
    e         : energy (current; target = 1.0)
    g         : global friction scalar
    n_windows : number of tick windows N in the composite sum
    ti        : current tick interval (for context — not used in Ti* calculation)
    """
    A = abs(z + x) * abs(1.0 - e)
    # Lower-bound B: each window contributes at minimum |2+x|·|g−e| ≥ 2·|g−e|
    B = n_windows * abs(2.0 + x) * abs(g - e)
    if B <= 1.0:
        return math.inf
    if A == 0.0:
        return 0.0
    return A / (B - 1.0)


# ---------------------------------------------------------------------------
# Prefeed quality gate — CSS / M3
# ---------------------------------------------------------------------------

def f_css(
    a_nw: float,
    delta: float,
    cc: float,
    z_prev: float,
    z: float,
    tcv: float,
    scop: float,
    e2: float,
    h2: float,
    e5: float,
    e1: float,
) -> float:
    """
    F_CSS:  CSS = A_nw · Δ · |Cc · (z_prev/z)| · |Tcv · SCOP / (e2 − H2)| · (Δ−E5) / [E1, 1]

    Coherence State Score — quality measure for a pending shuffle order.
    Scalar output: higher CSS = more deviation from the coherent attractor state.

    Parameters
    ----------
    a_nw   : resources (n_w weighted normalisation); treated as 1.0 proxy when unavailable
    delta  : change signal since last tick (Δ)
    cc     : consumption component (energy cost proxy)
    z_prev : previous SCOP z coordinate
    z      : current SCOP z coordinate (guarded ≠ 0)
    tcv    : tracer consensus value
    scop   : SCOP coordinate (scope measure)
    e2     : energy at MATH basin shard (proxy ≈ 3.92)
    h2     : height-squared component (H²)
    e5     : energy at COMMANDS basin shard (proxy ≈ 11.76)
    e1     : energy at CODE basin shard (proxy ≈ 3.92)
    """
    z_safe   = z      if abs(z)           > 1e-9 else 1e-9
    denom    = e2 - h2
    denom    = denom  if abs(denom)       > 1e-9 else 1e-9
    norm     = 1.0 - e1
    norm     = norm   if abs(norm)        > 1e-9 else 1e-9

    ratio    = abs(cc * (z_prev / z_safe))
    basin    = abs(tcv * scop / denom)
    delta_e5 = abs(delta - e5) / abs(norm)
    return a_nw * delta * ratio * basin * delta_e5


def f_m3(css: float, n: int, fast_formula: float, shi: float) -> float:
    """
    F_M3:  M3 = |CSS| · n · |FastFormula − SHI|

    Prefeed quality composite — gates SHUFFLE_NEXT commit.
    Low M3 → pending order is coherent and SHI-aligned → accept.
    High M3 → pending order is misaligned → discard and retry.

    Parameters
    ----------
    css          : coherence state score (output of f_css)
    n            : track count (N from snapshot; clamped ≥ 1)
    fast_formula : mean PFS harmonic resonance score of pending order
    shi          : Schema Health Index proxy (mean shard activation)
    """
    return abs(css) * max(n, 1) * abs(fast_formula - shi)


# ---------------------------------------------------------------------------
# Routing envelope bounds — Gap 5 (Sheet 5 from phi-routing-diagnosis-2026-08-04)
# ---------------------------------------------------------------------------


def f_envelope_max(
    a: float,
    w: float,
    z: float,
    c: float,
    k_consensus: float,
    v: float,
    i: int,
    beta_t: float,
) -> float:
    """
    F_ENVELOPE_MAX:  A_xmax = A^w · |z − 2c/K| · v · |i·v + 1| · βt

    Upper bound of the routing cost envelope.  Routing output must not exceed
    this value — clip modulated to max(modulated, A_xmax) is invalid;
    clip modulated to min(modulated, A_xmax) is the correct application.

    Parameters
    ----------
    a           : resources (n_w weighted); proxy = 1.0 when unavailable
    w           : resource exponent weight; proxy = 1.0
    z           : z_awareness (SCOP z-score of hub activation history)
    c           : consumption component; proxy = modulated output
    k_consensus : tracer consensus delta K; proxy = 1.0
    v           : velocity / gradient = |metric_raw − modulated|
    i           : shard index [0–7]
    beta_t      : pressure at time t (coherence proxy)
    """
    k_safe = k_consensus if abs(k_consensus) > 1e-9 else 1e-9
    return (a ** w) * abs(z - 2.0 * c / k_safe) * v * abs(i * v + 1.0) * beta_t


def f_envelope_min(
    k: float,
    r: float,
    g: float,
    z: float,
    x: float,
    beta_t: float,
    beta_h: float,
) -> float:
    """
    F_ENVELOPE_MIN:  A_xmin = k · |r·g| · |z − x/βt| − βH

    Lower bound of the routing cost envelope.  Can be negative — callers
    should apply max(0, A_xmin) as the effective floor when clipping.

    Parameters
    ----------
    k       : repair gain constant; proxy = COHERENCE_FLOOR (0.5)
    r       : rizomic coordinate; proxy = shard / (N_SHARDS − 1) ∈ [0, 1]
    g       : global friction; proxy = LOCAL_FRICTION (0.5)
    z       : z_awareness
    x       : modulated (confidence / Layer-1 output)
    beta_t  : coherence (pressure / SHI proxy)
    beta_h  : height pressure βH; proxy = COHERENCE_FLOOR (0.5)
    """
    beta_t_safe = beta_t if abs(beta_t) > 1e-9 else 1e-9
    return k * abs(r * g) * abs(z - x / beta_t_safe) - beta_h


# ---------------------------------------------------------------------------
# Soot-ash dynamics — edge volatility
# ---------------------------------------------------------------------------


def f_edge_volatility(edge_deltas: list[float], w: float = 1.0) -> float:
    """
    F_EDGE_VOLATILITY:  V_edge = std(|ΔT_edge|) + avg(|ΔT_edge|) · w

    Routing instability signal derived from shard activation changes between
    successive dispatcher steps.  High V_edge indicates that the harmonic ring
    is in a volatile (soot) phase — routes are shifting faster than the system
    can crystallise them.  The dispatcher uses V_edge to stretch τ so the
    coherence gate stays open longer and suppresses thrashing.

    Parameters
    ----------
    edge_deltas : per-shard absolute activation deltas |ΔT_edge| between
                  the last two shard snapshots
    w           : weighting scalar applied to the mean term (default 1.0)

    Returns
    -------
    V_edge ≥ 0.0 — zero when deltas are empty or all equal.
    """
    if not edge_deltas:
        return 0.0
    n = len(edge_deltas)
    mean = sum(edge_deltas) / n
    variance = sum((d - mean) ** 2 for d in edge_deltas) / n
    std = math.sqrt(variance)
    return std + mean * w


# ---------------------------------------------------------------------------
# Soot-ash dynamics — shimmer / crystallisation / ash yield
# ---------------------------------------------------------------------------


def f_shimmer_decay(
    A: float,
    lam: float,
    t: float,
    p: float,
    phi_hysteresis: float,
) -> float:
    """
    F_SHIMMER_DECAY:  shimmer_t = A · exp(−λ · t) + p · φ_hysteresis

    Exponential fade of the shimmer amplitude after an activity burst, with a
    pressure-weighted hysteresis floor that prevents complete collapse when the
    system is still under cognitive pressure.

    Parameters
    ----------
    A              : burst amplitude at t = 0
    lam            : shimmer decay rate λ > 0  (guarded against ≤ 0)
    t              : ticks elapsed since the burst
    p              : pressure signal (0 = quiescent, 1 = fully active)
    phi_hysteresis : hysteresis factor φ — scales the pressure floor

    Returns
    -------
    shimmer_t ≥ 0.0
    """
    lam_safe = lam if lam > 0.0 else 1e-9
    return A * math.exp(-lam_safe * t) + p * phi_hysteresis


def f_shimmer_base(
    A: float,
    tp_rar_t: float,
    eps: float,
    decay_coef: float,
    p: float,
    phi_hysteresis: float,
) -> float:
    """
    F_SHIMMER_BASE:  shimmer_base = δ(A − TP_RAR_t + ε/2 − decay_coef) + p · φ_hyst

    Crystallisation seed — a delta-function indicator on the amplitude threshold
    that fires exactly when the shimmer amplitude is within ε/2 of the reference
    point minus the decay coefficient.  The pressure-hysteresis term ensures a
    non-zero floor under load.

    The δ is approximated as a narrow Gaussian bell (σ = ε/2) so the function
    is differentiable and numerically stable.

    Parameters
    ----------
    A           : current shimmer amplitude
    tp_rar_t    : reference tracking point at time t  (TP_RAR_t)
    eps         : epsilon — width of the delta window
    decay_coef  : accumulated decay coefficient
    p           : pressure
    phi_hysteresis : hysteresis factor φ

    Returns
    -------
    shimmer_base ≥ 0.0
    """
    sigma = (eps / 2.0) if eps > 0.0 else 1e-9
    arg = A - tp_rar_t + eps / 2.0 - decay_coef
    delta_approx = math.exp(-(arg ** 2) / (2.0 * sigma ** 2))
    return delta_approx + p * phi_hysteresis


def f_crystallisation(eta: float, t_min: float, shimmerfield_t0: float) -> float:
    """
    F_CRYSTALLISATION:  C_thresh = η^t_min · shimmerfield_t0

    Power-law settling threshold — the shimmer field must decay below this value
    before the system is considered crystallised (route is stable, prefeed commit
    is allowed).  As t_min grows, C_thresh shrinks: more cooling ticks required
    for a larger initial burst.

    Parameters
    ----------
    eta            : learning rate η ∈ (0, 1) — per-tick decay factor
    t_min          : minimum ticks in the cool phase required for crystallisation
    shimmerfield_t0: shimmer amplitude at the start of the cool phase (t = 0)

    Returns
    -------
    C_thresh ≥ 0.0
    """
    eta_safe = max(min(float(eta), 1.0 - 1e-9), 1e-9)
    return (eta_safe ** t_min) * abs(shimmerfield_t0)


def f_ash_yield(A_base: float, k: float, T: float, T_min: float) -> float:
    """
    F_ASH_YIELD:  A_yield = A_base · exp(k · (T − T_min))

    Arrhenius-style ash production rate — exponential in the excess temperature
    above T_min.  When T ≤ T_min the yield collapses to A_base (baseline residue).
    Models the burst of ash produced when shard heat exceeds the minimum threshold.

    Parameters
    ----------
    A_base : baseline ash yield at T = T_min
    k      : growth coefficient (Arrhenius k > 0)
    T      : current edge temperature (proxy: V_edge or mean activation)
    T_min  : minimum temperature below which no excess ash forms

    Returns
    -------
    A_yield ≥ 0.0
    """
    return A_base * math.exp(k * (T - T_min))


def f_volcanic_ash(sigma: float, N_flow: float, dt: float) -> float:
    """
    F_VOLCANIC_ASH:  A_voc = σ · N_flow · dt

    Nutrient-flow reinforcement signal — volcanic ash accumulates when sustained
    nutrient flow (N_flow) is present.  The sigmoid output (σ) gates the signal
    so it saturates near 1.0 for high-flow conditions.

    Parameters
    ----------
    sigma  : sigmoid output of the routing layer ∈ [0, 1]
    N_flow : current nutrient flow rate
    dt     : time delta (step size)

    Returns
    -------
    A_voc ≥ 0.0
    """
    return sigma * N_flow * dt


# ---------------------------------------------------------------------------
# Emission gate — e5 Transformation Readiness Metric + supporting sigil layer
#
# Decision rule:
#   e5 >  0.1  →  OPEN     (surface / act)
#   e5 > -0.1  →  MARGINAL (borderline — can be nudged by context)
#   e5 < -0.1  →  BLOCKED  (system will not act regardless of K)
#
# Ohm's-law structure:
#   argument = (H + K) / (G − energy_dot) − Bc/20
#            = V / R − brake
#   V = H + K  (drive: system receptivity + hub kinetic energy)
#   R = G − energy_dot  (effective resistance: structural penalty − energy landscape)
#
# When R → 0 (G ≈ energy_dot) the argument diverges → tanh saturates to ±1.
# This is the critical point — maximum sensitivity, phase-transition behaviour.
#
# Load line:  the minimum V/R ratio required to open the gate at queue depth Bc is
#     V/R > arctanh(0.1) + Bc/20  ≈  0.1003 + Bc/20
# At full queue (Bc=20) the drive-to-resistance ratio must exceed ~1.1 to act.
# ---------------------------------------------------------------------------

#: Decision threshold — e5 must exceed this for the gate to be OPEN.
E5_OPEN_THRESHOLD: float = 0.1

#: arctanh(E5_OPEN_THRESHOLD) — fixed offset on the load line.
_E5_ARCTANH_THRESHOLD: float = math.atanh(E5_OPEN_THRESHOLD)  # ≈ 0.1003

#: Maximum queue depth at which the gate can still open (V/R → ∞ limit).
E5_BC_MAX: int = 20


def f_cc_energy_budget(
    capacity_ceiling: float,
    adaptive_capacity: float,
    pressure: float,
    tracer_consensus_value: float,
) -> float:
    """
    F_CC:  Cc = ((c − A) / p) · Tcv

    Available energy budget for transformation — how much energy the system
    can spend on surfacing a track, scaled by tracer consensus.

    Parameters
    ----------
    capacity_ceiling      : c   — maximum possible energy (system ceiling)
    adaptive_capacity     : A   — current adaptive capacity (F_ADAPTIVE_CAPACITY output)
    pressure              : p   — pressure scalar; guarded ≠ 0
    tracer_consensus_value: Tcv — tracer consensus ∈ [0, 1]

    Returns
    -------
    Cc (float) — energy budget available for this transformation step.
    """
    p = pressure if pressure != 0.0 else 1e-9
    return ((capacity_ceiling - adaptive_capacity) / p) * tracer_consensus_value


def f_k_sigil(H: float, Cc: float, G: float) -> float:
    """
    F_K_SIGIL:  k = (H + Cc) − G

    Sigil-layer transformation score — net readiness after subtracting
    structural resistance.

    k > 0: drive + budget exceeds resistance → transformation is viable.
    k < 0: resistance dominates → blocked regardless of queue state.

    This is a necessary but not sufficient condition for e5 > 0.

    Parameters
    ----------
    H  : height node output (F_HEIGHT_NODE)
    Cc : energy budget (f_cc_energy_budget)
    G  : structural penalty / global rzone (F_GLOBAL_RZONE)

    Returns
    -------
    k (float) — positive means viable, negative means blocked.
    """
    return (H + Cc) - G


def f_e5(
    H: float,
    K: float,
    G: float,
    energy_dot: float,
    Bc: int,
    bc_max: int = E5_BC_MAX,
) -> float:
    """
    F_E5 — Transformation Readiness Metric:
        e5 = tanh( (H + K) / (G − energy_dot) − Bc / bc_max )

    Ohm's-law emission gate.  The ratio (H + K) / (G − energy_dot) is the
    drive-to-resistance ratio (V/R).  The queue brake Bc/bc_max shifts the
    operating point linearly: a full queue demands V/R > ~1.1 to open the gate.

    Critical point: when G ≈ energy_dot the denominator → 0, the argument
    diverges, and tanh saturates to ±1.  This is a phase transition — maximum
    sensitivity.  Guard against exact zero via 1e-9 clamp.

    Decision thresholds (apply to return value):
        e5 >  0.1  →  OPEN     — surface track / act
        e5 > -0.1  →  MARGINAL — borderline
        e5 < -0.1  →  BLOCKED  — system will not act

    Parameters
    ----------
    H          : height node value (F_HEIGHT_NODE output)
    K          : hub kinetic injection (PhiHubRing.k_for_track() — combines
                 ENERGY, MOOD, CONTEXT shard activations for this track)
    G          : structural penalty (F_GLOBAL_RZONE output)
    energy_dot : [r, y] · En — dot product of the rhizome/SCOP vector with the
                 energy landscape.  Caller computes:
                 energy_dot = r * en_rhizome + y * en_scop
    Bc         : current queue depth (len(queue.queue)) — song-stack count
    bc_max     : queue saturation depth (default 20 — full brake at Bc=bc_max)

    Returns
    -------
    e5 ∈ (−1, 1)
    """
    denom = G - energy_dot
    if abs(denom) < 1e-9:
        # Critical point — saturate in the direction of (H + K)
        denom = math.copysign(1e-9, denom) if denom != 0.0 else 1e-9

    brake = Bc / max(bc_max, 1)
    return math.tanh((H + K) / denom - brake)


def f_e4(e5: float, z: float, Cc: float) -> float:
    """
    F_E4 — Node Readiness / Locality Gate:
        e4 = |e5 / (−z)| + Cc − 1

    Track-level emission gate that sits below f_e5.  e5 gates whether the
    system is ready at all; e4 gates whether *this specific track* should
    surface given its spatial coherence cost z.

    Locality semantics: when |z| is small (track is near the current listening
    state) the |e5/z| term amplifies — the track surfaces easily.  When |z| is
    large (far from context) the term is suppressed and Cc must compensate.

    Track emits when e4 > 0.

    Parameters
    ----------
    e5 : transformation readiness (output of f_e5)
    z  : SCOP coordinate — spatial coherence cost for this track (guarded ≠ 0)
    Cc : energy budget (f_cc_energy_budget) — exploration cost cover

    Returns
    -------
    e4 (float) — positive → track can surface, negative → suppressed.
    """
    z_safe = z if abs(z) > 1e-9 else math.copysign(1e-9, z) if z != 0.0 else 1e-9
    return abs(e5 / (-z_safe)) + Cc - 1.0


def e5_load_line(Bc: int, bc_max: int = E5_BC_MAX) -> float:
    """
    Song-stack load line: minimum V/R ratio required to open the e5 gate.

        V/R_min = arctanh(E5_OPEN_THRESHOLD) + Bc / bc_max
                ≈ 0.1003 + Bc / 20

    At Bc=0  (empty queue):  V/R > ~0.10
    At Bc=10 (half-full):    V/R > ~0.60
    At Bc=20 (full queue):   V/R > ~1.10

    The relationship is linear in queue depth — the song-stack applies
    a uniform resistance per queued track of 1/bc_max per unit V/R.

    Parameters
    ----------
    Bc     : current queue depth
    bc_max : saturation depth (default 20)

    Returns
    -------
    minimum V/R threshold (float)
    """
    return _E5_ARCTANH_THRESHOLD + Bc / max(bc_max, 1)
