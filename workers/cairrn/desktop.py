"""
CAIRRN desktop formula I/O containers and dispatcher.

DesktopFormulaInputs  — all optional inputs for the 14 desktop formulas
DesktopFormulaOutputs — computed outputs (None when inputs were absent)
run_desktop_formulas  — dispatches inputs → outputs, skipping missing fields

Note: mypy cannot narrow Optional[float] fields through all(v is not None)
guards; the arg-type errors in run_desktop_formulas are structural false
positives. All call sites are runtime-safe.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

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
    f_css,
    f_m3,
    f_energy_weighted_geom,
    f_composite_health_horizon,
)


@dataclass
class DesktopFormulaInputs:
    """
    Optional inputs for desktop formula computation.

    All fields default to None — pass only what is available.
    When None, the corresponding formula output is skipped.

    Layer X (composite/constraint): forecast_result, likelihood, possibility,
      opportunity_cost, temporal_validator, energy_available, confidence, scope,
      dawn_data, energy_cost, tick_interval
    Layer 1 (modulation): energies, desirability_costs, resources,
      dist_weighted_times, positive_normalisation, required_energy,
      current_position, performance, tracer_consensus_value, global_friction,
      current_mode, rzone_coordinate, pressure_gradient, SHI, local_friction,
      tick_weighted_sum, SCOP, pressure
    Layer 2 (sharding): current_node, current_objective, energy_to_move,
      boolean_temporal, location, energy_projected, ticks_to_move,
      distance_per_waypoint
    Layer 3 (coherence): semantic_distance, time_steps, tracer_at_n, tip_value
    -Z Space: semantic_matrix_value, partial_deriv_1, rizomic_distance,
      sigma_accumulator, z_activation, z_uncertainty
    """
    # Layer X
    forecast_result: Optional[float] = None
    likelihood: Optional[float] = None
    possibility: Optional[float] = None
    opportunity_cost: Optional[float] = None
    temporal_validator: Optional[float] = None
    energy_available: Optional[float] = None
    confidence: Optional[float] = None
    scope: Optional[float] = None
    dawn_data: Optional[float] = None
    energy_cost: Optional[float] = None
    tick_interval: Optional[int] = None
    # Layer 1
    energies: Optional[List[float]] = None
    desirability_costs: Optional[List[float]] = None
    resources: Optional[float] = None
    dist_weighted_times: Optional[List[float]] = None
    positive_normalisation: Optional[float] = None
    required_energy: Optional[float] = None
    current_position: Optional[float] = None
    performance: Optional[float] = None
    tracer_consensus_value: Optional[float] = None
    global_friction: Optional[float] = None
    current_mode: Optional[float] = None
    rzone_coordinate: Optional[float] = None
    pressure_gradient: Optional[float] = None
    SHI: Optional[float] = None
    local_friction: Optional[float] = None
    tick_weighted_sum: Optional[float] = None
    SCOP: Optional[float] = None
    pressure: Optional[float] = None
    # Layer 2
    current_node: Optional[float] = None
    current_objective: Optional[float] = None
    energy_to_move: Optional[float] = None
    boolean_temporal: Optional[int] = None
    location: Optional[float] = None
    energy_projected: Optional[float] = None
    ticks_to_move: Optional[int] = None
    distance_per_waypoint: Optional[List[float]] = None
    # Layer 3
    semantic_distance: Optional[float] = None
    time_steps: Optional[float] = None
    tracer_at_n: Optional[float] = None
    tip_value: Optional[float] = None
    # Layer 3 — tick-count-weighted δ₂ (F_DELTA_TWO_CT)
    # Requires semantic_distance + time_steps (shared with f_delta_two) + current_tick
    current_tick: Optional[int] = None      # CT — current session tick index (≥ 0)
    # -Z Space
    semantic_matrix_value: Optional[float] = None
    partial_deriv_1: Optional[float] = None
    rizomic_distance: Optional[float] = None
    sigma_accumulator: Optional[float] = None
    z_activation: Optional[float] = None   # A in −Z formula
    z_uncertainty: Optional[float] = None  # z in −Z formula (SCOP / uncertainty)
    # Z_geom / health horizon
    w_resource: Optional[float] = None          # resource philosophy ∈ [0,1]; 0=divide, 0.5=neutral, 1=multiply
    health_z: Optional[float] = None            # z_awareness (SCOP z-score)
    health_x: Optional[float] = None            # modulated / confidence
    health_e: Optional[float] = None            # energy (target = 1.0)
    health_g: Optional[float] = None            # global friction
    health_n_windows: Optional[int] = None      # N tick windows in Ψ′ sum
    health_ti: Optional[float] = None           # current tick interval
    # Layer X — Ti-windowed composite Ψ′ (F_CAIRRN_COMPOSITE_V2)
    # Fires when all six v2_* fields are present.
    v2_confidence: Optional[float] = None       # z — SCOP z-awareness
    v2_scope: Optional[float] = None            # x — scope coordinate
    v2_energy: Optional[float] = None           # e — energy_cost minus CAIRRN score
    v2_global_friction: Optional[float] = None  # g — global friction scalar
    v2_n_windows: Optional[int] = None          # N — active tick windows in sum
    v2_tick_interval: Optional[float] = None    # Ti — current tick interval
    # Prefeed quality gate (CSS / M3)
    css_a_nw: Optional[float] = None        # resources (n_w weighted)
    css_delta: Optional[float] = None       # change signal since last tick (Δ)
    css_cc: Optional[float] = None          # consumption component
    css_z_prev: Optional[float] = None      # previous SCOP z coordinate
    css_z: Optional[float] = None           # current SCOP z coordinate
    css_tcv: Optional[float] = None         # tracer consensus value
    css_scop: Optional[float] = None        # SCOP coordinate
    css_e2: Optional[float] = None          # MATH shard energy (basin 3.92)
    css_h2: Optional[float] = None          # height-squared (MATH secondary proxy)
    css_e5: Optional[float] = None          # COMMANDS shard energy (basin 11.76)
    css_e1: Optional[float] = None          # CODE shard energy normalization floor
    m3_n: Optional[int] = None             # track count N for M3 gate
    m3_fast_formula: Optional[float] = None # mean PFS harmonic resonance score
    m3_shi: Optional[float] = None          # SHI proxy for M3


@dataclass
class DesktopFormulaOutputs:
    """Computed desktop formula outputs (None when inputs were absent)."""
    # Layer X
    constraint_var: Optional[float] = None
    forecast_score: Optional[float] = None
    cairrn_composite: Optional[float] = None
    cairrn_composite_v2: Optional[float] = None  # Ψ′ Ti-windowed composite
    # Layer 1
    energy_weighted: Optional[float] = None
    energy_consumption: Optional[float] = None
    height_node: Optional[float] = None
    global_rzone: Optional[float] = None
    local_friction_d: Optional[float] = None
    # Layer 2
    scope_nav: Optional[float] = None
    location_route: Optional[float] = None
    # Layer 3
    delta_two: Optional[float] = None
    delta_two_ct: Optional[float] = None          # g2 — tick-count-weighted δ₂
    tracer_consensus_k: Optional[float] = None
    tick_wisdom: Optional[float] = None
    # -Z Space (full ZScore built in CAIRRNWorker._run)
    neg_z: Optional[float] = None
    # Z_geom / health horizon
    energy_weighted_geom: Optional[float] = None
    health_horizon: Optional[float] = None       # Ti* — max tick interval before Ψ′ < 0
    # Prefeed quality gate
    css: Optional[float] = None
    m3: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


def run_desktop_formulas(inp: DesktopFormulaInputs) -> DesktopFormulaOutputs:
    """
    Compute all desktop formulas for which inputs are present.

    Each formula is skipped silently when its required inputs are None.
    """
    out = DesktopFormulaOutputs()

    # Layer X — constraint variable
    if all(v is not None for v in (inp.likelihood, inp.possibility, inp.opportunity_cost)):
        out.constraint_var = f_constraint_var(inp.likelihood, inp.possibility, inp.opportunity_cost)

    # Layer X — forecast score (depends on constraint_var)
    xc = out.constraint_var
    if xc is None and all(v is not None for v in (inp.likelihood, inp.possibility, inp.opportunity_cost)):
        xc = f_constraint_var(inp.likelihood, inp.possibility, inp.opportunity_cost)
    if xc is not None and all(v is not None for v in (inp.forecast_result, inp.temporal_validator, inp.energy_available)):
        out.forecast_score = f_forecast_score(inp.forecast_result, xc, inp.temporal_validator, inp.energy_available)

    # Layer X — CAIRRN composite (single-tick, original)
    if all(v is not None for v in (inp.confidence, inp.scope, inp.dawn_data, inp.energy_cost, inp.tick_interval)):
        out.cairrn_composite = f_cairrn_composite(
            inp.confidence, inp.scope, inp.dawn_data, inp.energy_cost, inp.tick_interval,
        )

    # Layer X — CAIRRN composite v2 (Ti-windowed Ψ′)
    if all(v is not None for v in (
        inp.v2_confidence, inp.v2_scope, inp.v2_energy,
        inp.v2_global_friction, inp.v2_n_windows, inp.v2_tick_interval,
    )):
        out.cairrn_composite_v2 = f_cairrn_composite_v2(
            inp.v2_confidence, inp.v2_scope, inp.v2_energy,
            inp.v2_global_friction, inp.v2_n_windows, inp.v2_tick_interval,
        )

    # Layer 1 — energy weighted (divide form, w=0)
    if all(v is not None for v in (
        inp.energies, inp.desirability_costs, inp.resources,
        inp.dist_weighted_times, inp.positive_normalisation,
    )) and len(inp.energies) == len(inp.desirability_costs) == len(inp.dist_weighted_times):
        out.energy_weighted = f_energy_weighted(
            inp.energies, inp.desirability_costs, inp.resources,
            inp.dist_weighted_times, inp.positive_normalisation,
        )

    # Layer 1 — energy weighted geometric mean (Z_geom, w-parameterised)
    _w = inp.w_resource if inp.w_resource is not None else 0.5
    if all(v is not None for v in (
        inp.energies, inp.desirability_costs, inp.resources,
        inp.dist_weighted_times, inp.positive_normalisation,
    )) and len(inp.energies) == len(inp.desirability_costs) == len(inp.dist_weighted_times):
        out.energy_weighted_geom = f_energy_weighted_geom(
            inp.energies, inp.desirability_costs, inp.resources,
            inp.dist_weighted_times, inp.positive_normalisation,
            w=_w,
        )

    # Composite health horizon (Ti*) — max tick interval before Ψ′ < 0
    if all(v is not None for v in (
        inp.health_z, inp.health_x, inp.health_e,
        inp.health_g, inp.health_n_windows, inp.health_ti,
    )):
        out.health_horizon = f_composite_health_horizon(
            inp.health_z, inp.health_x, inp.health_e,
            inp.health_g, inp.health_n_windows, inp.health_ti,
        )

    # Layer 1 — energy consumption
    if all(v is not None for v in (
        inp.required_energy, inp.current_position, inp.temporal_validator,
        inp.performance, inp.tracer_consensus_value,
    )):
        out.energy_consumption = f_energy_consumption(
            inp.required_energy, inp.current_position,
            inp.temporal_validator, inp.performance, inp.tracer_consensus_value,
        )

    # Layer 1 — height node
    if all(v is not None for v in (inp.global_friction, inp.current_mode, inp.tracer_consensus_value)):
        out.height_node = f_height_node(inp.global_friction, inp.current_mode, inp.tracer_consensus_value)

    # Layer 1 — global R-zone
    if all(v is not None for v in (
        inp.rzone_coordinate, inp.pressure_gradient, inp.tracer_consensus_value, inp.SHI,
    )):
        out.global_rzone = f_global_rzone(
            inp.rzone_coordinate, inp.pressure_gradient, inp.tracer_consensus_value, inp.SHI,
        )

    # Layer 1 — local friction delta
    if all(v is not None for v in (
        inp.local_friction, inp.tick_weighted_sum, inp.confidence, inp.SCOP, inp.pressure,
    )):
        out.local_friction_d = f_local_friction_d(
            inp.local_friction, inp.tick_weighted_sum, inp.confidence, inp.SCOP, inp.pressure,
        )

    # Layer 2 — scope navigation
    if all(v is not None for v in (
        inp.current_node, inp.current_objective, inp.energy_to_move,
        inp.boolean_temporal, inp.SHI,
    )):
        out.scope_nav = f_scope_nav(
            inp.current_node, inp.current_objective, inp.energy_to_move,
            inp.boolean_temporal, inp.SHI,
        )

    # Layer 2 — location route
    if all(v is not None for v in (
        inp.location, inp.energy_projected, inp.ticks_to_move, inp.distance_per_waypoint,
    )):
        out.location_route = f_location_route(
            inp.location, inp.energy_projected, inp.ticks_to_move, inp.distance_per_waypoint,
        )

    # Layer 3 — delta two (original — pressure-gradient weighted)
    if all(v is not None for v in (
        inp.semantic_distance, inp.time_steps, inp.pressure_gradient, inp.opportunity_cost,
    )):
        out.delta_two = f_delta_two(
            inp.semantic_distance, inp.time_steps, inp.pressure_gradient, inp.opportunity_cost,
        )

    # Layer 3 — delta two CT (tick-count-weighted g2 — F_DELTA_TWO_CT)
    # Shares semantic_distance + time_steps with the above; needs current_tick additionally.
    if all(v is not None for v in (
        inp.semantic_distance, inp.time_steps, inp.current_tick,
    )):
        out.delta_two_ct = f_delta_two_ct(
            inp.semantic_distance, inp.time_steps, inp.current_tick,
        )

    # Layer 3 — tracer consensus K
    if all(v is not None for v in (inp.tracer_consensus_value, inp.SHI)):
        out.tracer_consensus_k = f_tracer_consensus_k(inp.tracer_consensus_value, inp.SHI)

    # Layer 3 — tick wisdom (depends on tracer_consensus_k)
    K = out.tracer_consensus_k
    if K is None and all(v is not None for v in (inp.tracer_consensus_value, inp.SHI)):
        K = f_tracer_consensus_k(inp.tracer_consensus_value, inp.SHI)
    if K is not None and all(v is not None for v in (inp.tracer_at_n, inp.tip_value)):
        out.tick_wisdom = f_tick_wisdom(inp.tracer_at_n, inp.tip_value, K)

    # -Z Space — raw neg_z stored here; full ZScore built in CAIRRNWorker._run
    _z_act = inp.z_activation
    _z_unc = inp.z_uncertainty if inp.z_uncertainty is not None else inp.SCOP
    _z_ec  = inp.energy_cost
    if all(v is not None for v in (
        inp.semantic_matrix_value, inp.partial_deriv_1,
        _z_act, _z_ec, _z_unc,
        inp.rizomic_distance, inp.sigma_accumulator,
    )):
        out.neg_z = f_cairrn_z_space(
            inp.semantic_matrix_value, inp.partial_deriv_1,
            _z_act, _z_ec, _z_unc,
            inp.rizomic_distance, inp.sigma_accumulator,
        )

    # Prefeed quality gate — CSS then M3
    if all(v is not None for v in (
        inp.css_a_nw, inp.css_delta, inp.css_cc,
        inp.css_z_prev, inp.css_z, inp.css_tcv, inp.css_scop,
        inp.css_e2, inp.css_h2, inp.css_e5, inp.css_e1,
    )):
        out.css = f_css(
            inp.css_a_nw, inp.css_delta, inp.css_cc,
            inp.css_z_prev, inp.css_z, inp.css_tcv, inp.css_scop,
            inp.css_e2, inp.css_h2, inp.css_e5, inp.css_e1,
        )

    css_val = out.css
    if css_val is not None and all(v is not None for v in (
        inp.m3_n, inp.m3_fast_formula, inp.m3_shi,
    )):
        out.m3 = f_m3(css=css_val, n=inp.m3_n, fast_formula=inp.m3_fast_formula, shi=inp.m3_shi)

    return out
