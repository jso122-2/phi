"""Simulation tools: double_well, neg_exp, sweep, ana_chi."""
from __future__ import annotations

from typing import Any

import numpy as np

from mcp_server._gate import requires_init
from mcp_server._state import _dom_queue, _harmonic_index, _vault_hub, mcp
from sims.ana_chi import (
    ANA_CHI_CONSTANT,
    BASINS as _ANA_CHI_BASINS,
    biphasic_signal as _ana_chi_biphasic,
    hub_chi_weights as _ana_chi_hub_weights,
    rattling_proximity as _ana_chi_rattling_proximity,
    run_ana_chi_flow as _run_ana_chi_flow,
    summarise_flow as _summarise_ana_chi_flow,
)
from sims.attractors import (
    ALPHA,
    kramers_rate,
    measure_mfpt,
    run_double_well,
    run_langevin,
    run_neg_exp_map,
    summarise,
    sweep_initial_conditions,
)


@mcp.tool()
@requires_init
def double_well_sim(
    x0: float,
    lr: float = 0.05,
    alpha: float = ALPHA,
    inject_into_index: bool = True,
) -> dict[str, Any]:
    """
    Run a double-well attractor simulation from starting point x0.

    V(x) = (x² - α²)²  has stable minima at ±α (default α = 1.96).
    Gradient descent converges to +α if x0 > 0, -α if x0 < 0.

    Parameters
    ----------
    x0                : initial position
    lr                : gradient-descent learning rate (default 0.05)
    alpha             : well locations ±α (default 1.96)
    inject_into_index : if True, inject final position into the harmonic index
    """
    with _dom_queue.gate("double_well_sim"):
        traj = run_double_well(x0, lr=lr, alpha=alpha)
        summary = summarise(traj, alpha=alpha)
        if inject_into_index:
            shard = _harmonic_index.inject_from_trajectory_final(traj.steps[-1])
            summary["injected_shard"] = shard.index
            summary["shard_basin_centre"] = shard.basin_centre
        _vault_hub.push_all(
            harmonic=_harmonic_index.state(),
            sim_tool="double_well_sim",
            sim_result=summary,
        )
        return summary


@mcp.tool()
@requires_init
def neg_exp_sim(x0: float) -> dict[str, Any]:
    """
    Iterate f(x) = −eˣ from starting point x0.

    Converges to the Lambert-W fixed point x* = −W(1) ≈ −0.5671
    because |f′(x*)| = W(1) ≈ 0.567 < 1.

    Parameters
    ----------
    x0 : initial position
    """
    with _dom_queue.gate("neg_exp_sim"):
        traj = run_neg_exp_map(x0)
        final_x = traj.steps[-1] if traj.steps else x0
        fixed_point = -0.5671432904097838
        result = {
            "x0":                    traj.x0,
            "steps":                 len(traj.steps),
            "final_x":               round(final_x, 8),
            "converged":             traj.converged,
            "lambert_w_fixed_point": fixed_point,
            "error_to_fixed_point":  round(abs(final_x - fixed_point), 8),
        }
        # Inject final position into the harmonic index so the Lambert-W
        # attractor shapes the search perspective (mirrors double_well_sim).
        shard = _harmonic_index.inject_from_trajectory_final(final_x)
        result["injected_shard"] = shard.index
        result["shard_basin_centre"] = shard.basin_centre
        _vault_hub.push_sim("neg_exp_sim", result)
        return result


@mcp.tool()
@requires_init
def sweep_attractors(
    x0_min: float = -4.0,
    x0_max: float = 4.0,
    n_points: int = 9,
    alpha: float = ALPHA,
    inject_into_index: bool = True,
) -> dict[str, Any]:
    """
    Sweep initial conditions across [x0_min, x0_max] for the double-well sim.

    Parameters
    ----------
    x0_min, x0_max   : sweep range
    n_points          : number of starting positions (linearly spaced)
    alpha             : well locations ±α
    inject_into_index : inject all final positions into the harmonic index
    """
    with _dom_queue.gate("sweep_attractors"):
        x0_values = list(np.linspace(x0_min, x0_max, n_points))
        trajectories = sweep_initial_conditions(x0_values, run_double_well, alpha=alpha)
        summaries = [summarise(t, alpha=alpha) for t in trajectories]
        if inject_into_index:
            for t in trajectories:
                if t.steps:
                    _harmonic_index.inject_from_trajectory_final(t.steps[-1])
        result = {
            "n_trajectories": len(summaries),
            "alpha":          alpha,
            "converged":      sum(1 for s in summaries if s["converged"]),
            "trajectories":   summaries,
        }
        _vault_hub.push_all(
            harmonic=_harmonic_index.state(),
            sim_tool="sweep_attractors",
            sim_result=result,
        )
        return result


@mcp.tool()
@requires_init
def ana_chi_sim(
    chi_0: float = ANA_CHI_CONSTANT,
    lr: float = 0.02,
    max_iter: int = 2000,
    modulate_index: bool = True,
) -> dict[str, Any]:
    """
    Run gradient descent on the 5-basin Ana-Chi potential from chi_0.

    Parameters
    ----------
    chi_0          : initial χ position (default 𝒜_χ = 1.5414)
    lr             : gradient-descent learning rate (default 0.02)
    max_iter       : iteration cap
    modulate_index : if True, apply Ana-Chi modulation to the harmonic index
    """
    with _dom_queue.gate("ana_chi_sim"):
        traj = _run_ana_chi_flow(chi_0, lr=lr, max_iter=max_iter)
        result = _summarise_ana_chi_flow(traj)
        result["harmonic_modulation"] = (
            _harmonic_index.ana_chi_modulate(result["final_chi"])
            if modulate_index else None
        )
        _vault_hub.push_all(
            harmonic=_harmonic_index.state(),
            sim_tool="ana_chi_sim",
            sim_result=result,
        )
        return result


@mcp.tool()
@requires_init
def langevin_sim(
    x0: float,
    noise_scale: float = 2.0,
    steps: int = 500,
    lr: float = 0.05,
    alpha: float = ALPHA,
    seed: int | None = None,
) -> dict[str, Any]:
    """
    Overdamped Langevin dynamics on V(x) = (x² − α²)².

    Unlike deterministic double_well_sim, noise allows thermally-activated
    escape between the ±α wells. Set noise_scale=0 to recover pure gradient
    descent. Final position is injected into the harmonic index.

    Parameters
    ----------
    x0          : initial position
    noise_scale : √D noise amplitude (D = diffusion coefficient)
    steps       : number of Langevin steps to run
    lr          : step size
    alpha       : well locations ±α (default 1.96)
    seed        : RNG seed for reproducibility
    """
    with _dom_queue.gate("langevin_sim"):
        traj = run_langevin(x0, noise_scale=noise_scale, lr=lr,
                            max_iter=steps, alpha=alpha, seed=seed)
        final = traj.steps[-1] if traj.steps else x0
        basin = "+α" if final > 0 else "-α"
        shard = _harmonic_index.inject_from_trajectory_final(final)
        k = kramers_rate(noise_scale, lr=lr, alpha=alpha)
        result: dict[str, Any] = {
            "x0":               x0,
            "noise_scale":      noise_scale,
            "D":                noise_scale ** 2,
            "steps_run":        len(traj.steps),
            "final_x":          round(final, 6),
            "final_basin":      basin,
            "n_zero_crossings": sum(
                1 for i in range(1, len(traj.steps))
                if traj.steps[i - 1] * traj.steps[i] < 0
            ),
            "kramers_tau_steps": round(k["tau_steps"], 1) if k["tau_steps"] != float("inf") else None,
            "injected_shard":    shard.index,
            "shard_basin_centre": shard.basin_centre,
        }
        _vault_hub.push_all(
            harmonic=_harmonic_index.state(),
            sim_tool="langevin_sim",
            sim_result=result,
        )
        return result


# Slash-only — Cursor catalog cap 60. Call via run_command("/mfpt").
@requires_init
def mfpt_estimate(
    noise_scale: float = 2.0,
    n_trials: int = 200,
    seed: int | None = None,
) -> dict[str, Any]:
    """
    Empirical mean first passage time (MFPT) vs Kramers prediction.

    Runs n_trials independent Langevin trajectories from x₀ = +α and
    measures the mean step count to first escape (x < 0). Compares the
    result to the analytical Kramers formula:

        τ = (2π / ω₀·ωₛ) · exp(ΔV / D)

    which is the exact solution to the MFPT integral:

        τ = λ ∫₀^∞ t · e^{−λt} dt = 1/λ

    Practical guidance on noise_scale:
        ΔV = α⁴ ≈ 14.75 for α = 1.96
        noise_scale ≥ 2.0  →  ΔV/D ≤ 3.7  →  escapes occur in < 10k steps
        noise_scale ≥ 3.0  →  ΔV/D ≤ 1.6  →  fast escape (Kramers approx. breaks down)
        noise_scale < 1.5  →  ΔV/D > 6.6  →  most trials will be censored

    Parameters
    ----------
    noise_scale : √D noise amplitude
    n_trials    : number of independent escape trials (default 200)
    seed        : RNG seed
    """
    with _dom_queue.gate("mfpt_estimate"):
        result = measure_mfpt(
            noise_scale=noise_scale,
            n_trials=n_trials,
            seed=seed,
        )
        k = kramers_rate(noise_scale)
        result["kramers_rate"] = k["rate"]
        result["kramers_exponent_delta_V_over_D"] = k["exponent"]
        result["kramers_omega_0"] = k["omega_0"]
        result["kramers_omega_s"] = k["omega_s"]
        _vault_hub.push_sim("mfpt_estimate", result)
        return result


# Slash-only — Cursor catalog cap 60. Call via run_command("/ana-chi-state").
@requires_init
def ana_chi_state(chi: float | None = None) -> dict[str, Any]:
    """
    Return the current Ana-Chi state of the harmonic index.

    If chi is provided, computes the biphasic signal and rattling proximity
    for that χ value. If None, uses the dominant hub's Ana-Chi basin χ.
    """
    with _dom_queue.gate("ana_chi_state"):
        index_state = _harmonic_index.ana_chi_state()
        effective_chi = chi if chi is not None else index_state["chi"]
        activated = [
            h for h, v in index_state["hub_activations"].items() if v > 0.01
        ]
        return {
            **index_state,
            "biphasic":          _ana_chi_biphasic(effective_chi),
            "rattling_proximity": _ana_chi_rattling_proximity(effective_chi),
            "hub_chi_weights":   _ana_chi_hub_weights(activated),
            "basins": [
                {
                    "name":         b.name,
                    "chi":          b.chi,
                    "gravity":      b.gravity,
                    "rattling":     b.rattling,
                    "colour":       b.colour,
                    "memory_decay": b.memory_decay,
                }
                for b in _ANA_CHI_BASINS
            ],
        }
