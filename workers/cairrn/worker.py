"""
CAIRRN worker classes — CAIRRNWorker, CAIRRNBatch, and supporting utilities.

CAIRRNWorker wraps any callable and runs it through the three-layer pipeline
(plus optional active -Z scoring when Z-space inputs are provided).
CAIRRNBatch spins one worker per hub and runs them simultaneously.
"""
from __future__ import annotations

import math
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from sims.attractors import NEG_EXP_FIXED_POINT, neg_exp
from sims.ana_chi import basin_at_hub
from workers.base import Worker, WorkerResult, Status
from workers.cairrn._constants import (
    N_SHARDS,
    _MAX_NEG_EXP_RAW,
    _COHERENCE_THRESHOLD,
    _HUB_PRIMARY_SHARD,
)
from workers.cairrn.layers import (
    ModulationResult,
    ShardSignal,
    CoherenceResult,
    ana_chi_modulate,
    neg_exp_shard,
    measure_coherence,
)
from workers.cairrn.desktop import (
    DesktopFormulaInputs,
    DesktopFormulaOutputs,
    run_desktop_formulas,
)
from workers.cairrn.z_space import ZScore, compute_z_score


# ---------------------------------------------------------------------------
# CAIRRNResult
# ---------------------------------------------------------------------------

@dataclass
class CAIRRNResult:
    """Full three-layer processing result attached to every CAIRRNWorker run."""
    hub: str
    modulation: ModulationResult
    shard_signal: ShardSignal
    coherence: CoherenceResult
    desktop: DesktopFormulaOutputs
    z_score: Optional[ZScore] = None
    re_routed: bool = False
    re_route_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        mod = self.modulation
        sig = self.shard_signal
        coh = self.coherence
        base = {
            # SKILL Layer 1 — Ana-Chi Modulation
            "layer_1": {
                "basin":            mod.basin_name,
                "chi":              mod.chi,
                "gravity":          mod.gravity,
                "rattling":         mod.rattling,
                "memory_decay":     mod.memory_decay,
                "raw_metric":       mod.raw_metric,
                "modulated_metric": mod.modulated_metric,
            },
            # SKILL Layer 2 — neg_exp Sharding
            "layer_2": {
                "neg_exp_one_step": sig.neg_exp_one_step,
                "natural_shard":    sig.natural_shard,
                "target_shard":     sig.target_shard,
                "shard_mismatch":   sig.shard_mismatch,
                "conv_steps":       sig.conv_steps,
                "conv_final":       sig.conv_final,
                "converged":        sig.converged,
            },
            # SKILL Layer 3 — Coherence Enforcement  exp(-steps/τ)
            "layer_3": {
                "coherence":            round(coh.coherence, 6),
                "coherent":             coh.coherent,
                "tau":                  round(coh.tau, 6),
                "steps":                round(coh.error_to_fixed_point, 8),
                "x_one_step":           coh.x_one_step,
                "fixed_point":          coh.fixed_point,
                "ana_chi_coherence":    coh.ana_chi_coherence,
            },
            # Routing outcome
            "hub":             self.hub,
            "re_routed":       self.re_routed,
            "re_route_reason": self.re_route_reason,
            # Flat aliases kept for backwards compatibility
            "basin":                mod.basin_name,
            "chi":                  mod.chi,
            "raw_metric":           mod.raw_metric,
            "modulated_metric":     mod.modulated_metric,
            "gravity":              mod.gravity,
            "rattling":             mod.rattling,
            "neg_exp_one_step":     sig.neg_exp_one_step,
            "natural_shard":        sig.natural_shard,
            "target_shard":         sig.target_shard,
            "shard_mismatch":       sig.shard_mismatch,
            "conv_steps":           sig.conv_steps,
            "conv_final":           sig.conv_final,
            "converged":            sig.converged,
            "coherence":            round(coh.coherence, 6),
            "coherent":             coh.coherent,
            "ana_chi_coherence":    coh.ana_chi_coherence,
            "x_one_step":           coh.x_one_step,
            "error_to_fixed_point": coh.error_to_fixed_point,
            "fixed_point":          coh.fixed_point,
        }
        if self.z_score is not None:
            base["z_active"]    = True
            base["neg_z"]       = self.z_score.neg_z
            base["z_shard"]     = self.z_score.z_shard
            base["z_coherence"] = self.z_score.z_coherence
            base["z_coherent"]  = self.z_score.z_coherent
        desktop = self.desktop.to_dict()
        if desktop:
            base["desktop"] = desktop
        return base


# ---------------------------------------------------------------------------
# CAIRRNWorker
# ---------------------------------------------------------------------------

class CAIRRNWorker(Worker):
    """
    A Worker anchored to a CAIRRN station hub.

    Wraps any callable and applies the CAIRRN three-layer pipeline every run:
      1. Ana-Chi modulation — basin gravity × rattling dampening
           modulated = metric × gravity × (memory_decay  if rattling)
      2. neg_exp sharding   — maps basin χ to natural shard via −e^χ
           shard = floor(e^χ × 8 / 14.44)  clamped [0, 7]
      3. Coherence gate     — exp(−steps/τ) ≥ W(1) or re-route to HOME
           steps = |f(χ) − x*|,  τ = _TAU ≈ 7.23,  x* = −W(1) ≈ −0.5671

    Optional layer (fires when Z-space inputs are provided):
      0. Active -Z scoring  — F_CAIRRN_Z_SPACE; coherence = min(layer3, z_coh)

    Desktop formulas (from DesktopFormulaInputs when provided) run in parallel
    with the three layers and populate DesktopFormulaOutputs in the result.

    Parameters
    ----------
    name                : human-readable label
    fn                  : callable to run
    hub_name            : CAIRRN hub (HOME / MATH / CODE / COMMANDS / agent-context)
    coherence_threshold : minimum coherence to accept output (default 0.50)
    re_route_hub        : fallback hub when incoherent (default HOME)
    desktop_inputs      : optional DesktopFormulaInputs
    """

    def __init__(
        self,
        name: str,
        fn: Callable[..., Any],
        hub_name: str,
        coherence_threshold: float = _COHERENCE_THRESHOLD,
        re_route_hub: str = "HOME",
        desktop_inputs: Optional[DesktopFormulaInputs] = None,
    ) -> None:
        super().__init__(name, fn)
        if hub_name not in _HUB_PRIMARY_SHARD:
            raise ValueError(
                f"Unknown CAIRRN hub {hub_name!r}. "
                f"Valid: {list(_HUB_PRIMARY_SHARD)}"
            )
        self.hub_name = hub_name
        self.coherence_threshold = coherence_threshold
        self.re_route_hub = re_route_hub
        self.desktop_inputs: Optional[DesktopFormulaInputs] = desktop_inputs
        self._cairrn_log: list[CAIRRNResult] = []

    def _run(self, *args: Any, **kwargs: Any) -> WorkerResult:
        try:
            raw_value = self._fn(*args, **kwargs)
            base_status = Status.DONE
            base_error: Optional[str] = None
        except Exception:
            raw_value = None
            base_status = Status.FAILED
            base_error = traceback.format_exc()

        metric = _extract_metric(raw_value) if base_status == Status.DONE else 0.0

        mod    = ana_chi_modulate(metric, self.hub_name)
        signal = neg_exp_shard(self.hub_name)
        # Late-bound so tests can patch workers.cairrn.measure_coherence
        import workers.cairrn as _pkg
        coh    = _pkg.measure_coherence(signal)

        desktop_inp = self.desktop_inputs or DesktopFormulaInputs()
        desktop_out = run_desktop_formulas(desktop_inp)

        z_score: Optional[ZScore] = None
        effective_coherence = coh.coherence
        if desktop_out.neg_z is not None:
            z_score = compute_z_score(
                semantic_matrix_value=desktop_inp.semantic_matrix_value,
                partial_deriv_1=desktop_inp.partial_deriv_1,
                activation=desktop_inp.z_activation,
                energy_cost=desktop_inp.energy_cost,
                uncertainty=(
                    desktop_inp.z_uncertainty
                    if desktop_inp.z_uncertainty is not None
                    else (desktop_inp.SCOP or 0.0)
                ),
                rizomic_distance=desktop_inp.rizomic_distance,
                sigma_accumulator=desktop_inp.sigma_accumulator,
                coherence_threshold=self.coherence_threshold,
            )
            effective_coherence = min(coh.coherence, z_score.z_coherence)

        re_routed = False
        re_route_reason = ""
        effective_hub = self.hub_name

        if effective_coherence < self.coherence_threshold and base_status == Status.DONE:
            re_routed = True
            effective_hub = self.re_route_hub
            z_tag = f", z_coherence={z_score.z_coherence:.4f}" if z_score else ""
            re_route_reason = (
                f"coherence {effective_coherence:.4f} < threshold {self.coherence_threshold:.2f}"
                f"{z_tag}; re-routed to {self.re_route_hub}"
            )

        cairrn = CAIRRNResult(
            hub=effective_hub,
            modulation=mod,
            shard_signal=signal,
            coherence=coh,
            desktop=desktop_out,
            z_score=z_score,
            re_routed=re_routed,
            re_route_reason=re_route_reason,
        )
        self._cairrn_log.append(cairrn)

        return WorkerResult(
            status=base_status,
            value={"value": raw_value, "cairrn": cairrn.to_dict()},
            error=base_error,
        )

    @property
    def cairrn_log(self) -> list[CAIRRNResult]:
        return list(self._cairrn_log)

    def shard_summary(self) -> dict[str, Any]:
        """Aggregated sharding and coherence statistics across all runs."""
        if not self._cairrn_log:
            return {"runs": 0}
        coherences = [c.coherence.coherence for c in self._cairrn_log]
        mismatches = sum(1 for c in self._cairrn_log if c.shard_signal.shard_mismatch)
        re_routes  = sum(1 for c in self._cairrn_log if c.re_routed)
        summary: dict[str, Any] = {
            "runs":              len(self._cairrn_log),
            "hub":               self.hub_name,
            "target_shard":      _HUB_PRIMARY_SHARD[self.hub_name],
            "natural_shard":     self._cairrn_log[-1].shard_signal.natural_shard,
            "mean_coherence":    round(sum(coherences) / len(coherences), 6),
            "min_coherence":     round(min(coherences), 6),
            "shard_mismatches":  mismatches,
            "re_routes":         re_routes,
            "last_neg_exp_step": self._cairrn_log[-1].shard_signal.neg_exp_one_step,
            "fixed_point":       NEG_EXP_FIXED_POINT,
        }
        z_runs = [c for c in self._cairrn_log if c.z_score is not None]
        if z_runs:
            z_cohs = [c.z_score.z_coherence for c in z_runs]
            summary["z_active_runs"]    = len(z_runs)
            summary["last_neg_z"]       = z_runs[-1].z_score.neg_z
            summary["last_z_shard"]     = z_runs[-1].z_score.z_shard
            summary["mean_z_coherence"] = round(sum(z_cohs) / len(z_cohs), 6)
            summary["min_z_coherence"]  = round(min(z_cohs), 6)
        return summary

    def __repr__(self) -> str:
        status = self.last.status.name if self.last else "PENDING"
        return (
            f"<CAIRRNWorker hub={self.hub_name!r} "
            f"status={status} runs={len(self._history)}>"
        )


# ---------------------------------------------------------------------------
# CAIRRNBatch
# ---------------------------------------------------------------------------

class CAIRRNBatch:
    """
    Spin up one CAIRRNWorker per CAIRRN hub and run them all.

    Parameters
    ----------
    fn                  : callable shared across all five workers
    coherence_threshold : forwarded to each CAIRRNWorker
    desktop_inputs      : optional DesktopFormulaInputs (same for all hubs)
    """

    HUBS: tuple[str, ...] = ("HOME", "MATH", "CODE", "COMMANDS", "agent-context")

    def __init__(
        self,
        fn: Callable[..., Any],
        coherence_threshold: float = _COHERENCE_THRESHOLD,
        desktop_inputs: Optional[DesktopFormulaInputs] = None,
    ) -> None:
        self._workers: dict[str, CAIRRNWorker] = {
            hub: CAIRRNWorker(
                name=f"cairrn-{hub.lower().replace('-', '_')}",
                fn=fn,
                hub_name=hub,
                coherence_threshold=coherence_threshold,
                desktop_inputs=desktop_inputs,
            )
            for hub in self.HUBS
        }

    def run_all(self, *args: Any, **kwargs: Any) -> dict[str, WorkerResult]:
        return {hub: w.run(*args, **kwargs) for hub, w in self._workers.items()}

    def summary(self) -> dict[str, Any]:
        return {hub: w.shard_summary() for hub, w in self._workers.items()}

    def coherence_map(self) -> dict[str, float]:
        """Current coherence score per hub (based on last run)."""
        result: dict[str, float] = {}
        for hub, w in self._workers.items():
            if w.cairrn_log:
                result[hub] = w.cairrn_log[-1].coherence.coherence
        return result


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _extract_metric(value: Any) -> float:
    """
    Best-effort extraction of a float metric from a worker return value.

    Priority:
      1. float / int directly
      2. dict with 'metric', 'score', 'value', 'error_to_attractor', or 'converged' key
      3. list / tuple → mean of numeric elements
      4. Fallback: 1.0 (neutral, passes Cerberus cleanly)
    """
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("metric", "score", "value", "error_to_attractor", "coherence"):
            v = value.get(key)
            if isinstance(v, (int, float)):
                return float(v)
        if "converged" in value:
            return 1.0 if value["converged"] else 0.0
    if isinstance(value, (list, tuple)):
        nums = [x for x in value if isinstance(x, (int, float))]
        if nums:
            return sum(nums) / len(nums)
    return 1.0


def spawn_hub_worker(
    hub_name: str,
    fn: Callable[..., Any],
    name: Optional[str] = None,
    coherence_threshold: float = _COHERENCE_THRESHOLD,
    desktop_inputs: Optional[DesktopFormulaInputs] = None,
) -> CAIRRNWorker:
    """
    Convenience factory: create a CAIRRNWorker anchored to hub_name.

    Parameters
    ----------
    hub_name        : CAIRRN hub
    fn              : callable
    name            : worker label (default: cairrn-<hub>)
    desktop_inputs  : optional DesktopFormulaInputs
    """
    label = name or f"cairrn-{hub_name.lower().replace('-', '_')}"
    return CAIRRNWorker(
        name=label,
        fn=fn,
        hub_name=hub_name,
        coherence_threshold=coherence_threshold,
        desktop_inputs=desktop_inputs,
    )


def _build_static_shard_map() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for hub in ("HOME", "MATH", "CODE", "COMMANDS", "agent-context"):
        basin = basin_at_hub(hub)
        chi = basin.chi
        one_step = neg_exp(chi)
        raw = math.exp(chi)
        nat = min(int(raw * N_SHARDS / _MAX_NEG_EXP_RAW), N_SHARDS - 1)
        rows[hub] = {
            "basin":         basin.name,
            "chi":           chi,
            "neg_exp_chi":   round(one_step, 6),
            "natural_shard": nat,
            "target_shard":  _HUB_PRIMARY_SHARD[hub],
        }
    return rows


STATIC_SHARD_MAP: dict[str, dict[str, Any]] = _build_static_shard_map()
