"""CAIRRN tools: hub geometry, single-hub run, batch run, CSS/M3 quality gate."""
from __future__ import annotations

from typing import Any

from mcp_server._gate import requires_init
from mcp_server._state import (
    _adaptive_confidence,
    _adaptive_consumption,
    _dom_queue,
    _harmonic_index,
    _temporal_index,
    _vault_hub,
    mcp,
    set_cairrn_coherence,
)
from sims.temporal import CAIRRN_HUBS as _CAIRRN_HUBS
from workers.cairrn import (
    CAIRRNBatch,
    DesktopFormulaInputs,
    NEG_EXP_FIXED_POINT as _NEG_EXP_FIXED_POINT,
    STATIC_SHARD_MAP,
    _COHERENCE_SIGMA as _CAIRRN_COHERENCE_SIGMA,
    _COHERENCE_THRESHOLD as _CAIRRN_COHERENCE_THRESHOLD,
    _TAU as _CAIRRN_TAU,
    f_tracer_consensus_k as _f_tracer_consensus_k,
    f_tick_wisdom as _f_tick_wisdom,
    measure_coherence,
    neg_exp_shard,
    spawn_hub_worker,
)
from engine.cairrn_dispatch import M3_THRESHOLD as _M3_THRESHOLD, _compute_m3

# ---------------------------------------------------------------------------
# CSS bitmask patterns (from css-m3-prefeed-gate-2026-08-04.md)
# Defined over middle 6 shards (1–6), excluding boundary shards 0 and 7.
# Each tuple: (bitmask_str, frozenset of hot shard indices, label)
# ---------------------------------------------------------------------------
_CSS_PATTERNS: list[tuple[str, frozenset, str]] = [
    ("101010", frozenset({1, 3, 5}), "alternating — CODE+MATH+COMMANDS — stable attractor"),
    ("110101", frozenset({1, 2, 4, 6}), "complementary pair"),
    ("101011", frozenset({1, 3, 5, 6}), "even + upper boundary"),
    ("101101", frozenset({1, 3, 4, 6}), "even + shard 3 hot"),
]
_CSS_STABLE_BITMASK = "101010"
_CSS_MIDDLE_SHARDS  = (1, 2, 3, 4, 5, 6)

# K coupling constant — matches harmonic propagation κ (keeps injection damped)
_K_COUPLING: float = 0.15


def _k_inject(
    tcv: float,
    hub_name: str = "agent-context",
    *,
    scale: float = _K_COUPLING,
    propagate: bool = True,
) -> dict[str, Any]:
    """
    Compute K = |Tcv| − SHI and inject K·scale into hub_name shards.

    K is the positive attractor score for the MCP session: it measures how
    useful the current signal is relative to the ring's resting state (SHI).
    When K > 0 the ring pulls toward the active hub; when K ≤ 0 nothing
    is injected (neutral / inhibitory signals are discarded).

    Parameters
    ----------
    tcv       : tracer consensus value (session coherence or content coherence)
    hub_name  : hub whose shards receive the K-scaled injection
    scale     : injection weight (default κ = 0.15)
    propagate : whether to run one local propagation step after injection

    Returns
    -------
    K, SHI, injected flag, injection value — for inclusion in tool result dicts.
    """
    if _harmonic_index is None:
        return {"K": None, "error": "harmonic_index_unavailable"}
    activations  = [s.activation for s in _harmonic_index.shards]
    shi          = sum(activations) / max(len(activations), 1)
    K            = abs(tcv) - shi
    inject_val   = K * scale
    did_inject   = False
    if K > 0:
        _harmonic_index.inject_from_hub(hub_name, value=inject_val)
        if propagate:
            _harmonic_index.propagate(steps=1, mode="local")
        did_inject = True
    return {
        "K":          round(K, 8),
        "SHI":        round(shi, 6),
        "tcv":        round(tcv, 8),
        "hub":        hub_name,
        "inject_val": round(inject_val, 8) if did_inject else 0.0,
        "injected":   did_inject,
    }


@mcp.tool()
@requires_init
def cairrn_hub_state() -> dict[str, Any]:
    """
    Report the static CAIRRN shard geometry across all five station hubs.

    For each hub: Ana-Chi basin χ, one-step neg_exp output, natural shard,
    target shard, coherence score, and Lambert-W fixed point distance.
    """
    with _dom_queue.gate("cairrn_hub_state"):
        hubs_out: dict[str, Any] = {}
        for hub, static in STATIC_SHARD_MAP.items():
            signal = neg_exp_shard(hub)
            coh = measure_coherence(signal)
            hubs_out[hub] = {
                **static,
                "conv_steps":           signal.conv_steps,
                "conv_final":           signal.conv_final,
                "converged":            signal.converged,
                "shard_mismatch":       signal.shard_mismatch,
                "coherence":            coh.coherence,
                "coherent":             coh.coherent,
                "error_to_fixed_point": coh.error_to_fixed_point,
            }
        return {
            "hubs":                hubs_out,
            "neg_exp_fixed_point": _NEG_EXP_FIXED_POINT,
            "coherence_sigma":     _CAIRRN_COHERENCE_SIGMA,
            "coherence_threshold": _CAIRRN_COHERENCE_THRESHOLD,
            "n_shards":            8,
        }


@mcp.tool()
@requires_init
def cairrn_hub_run(
    hub_name: str,
    metric: float = 1.0,
    semantic_matrix_value: float | None = None,
    partial_deriv_1: float | None = None,
    z_activation: float | None = None,
    z_energy_cost: float | None = None,
    z_uncertainty: float | None = None,
    rizomic_distance: float | None = None,
    sigma_accumulator: float | None = None,
    confidence: float | None = None,
    SHI: float | None = None,
    scope: float | None = None,
    pressure: float | None = None,
) -> dict[str, Any]:
    """
    Run the full CAIRRN four-layer pipeline for a given hub and metric.

    Layers: 1=Ana-Chi modulation | 2=neg_exp sharding | 3=coherence enforcement
            4=active -Z scoring (fires when all 7 Z-space inputs are given).

    Parameters
    ----------
    hub_name : HOME | MATH | CODE | COMMANDS | agent-context
    metric   : raw float metric to process (default 1.0)
    (see full docstring for Z-space and desktop formula parameters)
    """
    with _dom_queue.gate("cairrn_hub_run"):
        valid = ("HOME", "MATH", "CODE", "COMMANDS", "agent-context")
        if hub_name not in valid:
            return {"error": "unknown_hub", "hub_name": hub_name, "valid": list(valid)}

        # Adaptive fill-in: use CAIRRN self-judged confidence and mycelial
        # credit activation when the caller does not provide an override.
        eff_confidence = confidence if confidence is not None else _adaptive_confidence()
        eff_energy_cost = z_energy_cost if z_energy_cost is not None else _adaptive_consumption()

        desktop_inputs = DesktopFormulaInputs(
            confidence=eff_confidence, SHI=SHI, scope=scope, pressure=pressure,
            energy_cost=eff_energy_cost, SCOP=scope,
            semantic_matrix_value=semantic_matrix_value,
            partial_deriv_1=partial_deriv_1,
            rizomic_distance=rizomic_distance,
            sigma_accumulator=sigma_accumulator,
            z_activation=z_activation,
            z_uncertainty=z_uncertainty,
        )

        worker = spawn_hub_worker(hub_name, fn=lambda: metric, desktop_inputs=desktop_inputs)
        worker.run()
        cairrn = worker._cairrn_log[-1]
        effective_hub = cairrn.hub

        # Write back CAIRRN self-judged coherence for the next call's confidence.
        set_cairrn_coherence(cairrn.coherence.coherence)

        # Inject into the EFFECTIVE hub (post-reroute) and settle activation
        _harmonic_index.inject_from_hub(effective_hub, value=cairrn.modulation.modulated_metric)
        _harmonic_index.propagate(steps=2, mode="local")
        idx_state = _harmonic_index.state()

        if effective_hub in _CAIRRN_HUBS:
            _temporal_index.record(effective_hub, value=cairrn.modulation.modulated_metric)

        # K attractor injection — scores usefulness of this hub call against SHI.
        # propagate=False: propagation already ran above.
        k_meta = _k_inject(cairrn.coherence.coherence, hub_name=effective_hub, propagate=False)

        _vault_hub.push_harmonic(idx_state)

        result = cairrn.to_dict()

        # SKILL-aligned summary for display (Layer 1 / 2 / 3 report)
        mod = cairrn.modulation
        sig = cairrn.shard_signal
        coh = cairrn.coherence
        skill_summary = {
            "hub":       hub_name,
            "metric":    metric,
            "layer_1_ana_chi": (
                f"{metric} × {mod.gravity}"
                + (f" × {mod.memory_decay}" if mod.rattling else "")
                + f" = {mod.modulated_metric}"
            ),
            "layer_2_shard": (
                f"e^{mod.chi} × 8/14.44 → natural={sig.natural_shard}"
                f"  target={sig.target_shard}"
                + (" (mismatch)" if sig.shard_mismatch else "")
            ),
            "layer_3_coherence": (
                f"exp(−{coh.error_to_fixed_point:.4f}/{coh.tau:.4f})"
                f" = {coh.coherence:.6f}"
                + (" ✓" if coh.coherent else f" ✗ → re-routed to {cairrn.hub}")
            ),
            "injected": f"shard {sig.target_shard} → {mod.modulated_metric}",
        }

        result.update({
            "requested_hub":       hub_name,
            "skill_summary":       skill_summary,
            "neg_exp_fixed_point": _NEG_EXP_FIXED_POINT,
            "coherence_tau":       _CAIRRN_TAU,
            "coherence_sigma":     _CAIRRN_COHERENCE_SIGMA,
            "coherence_threshold": _CAIRRN_COHERENCE_THRESHOLD,
            "harmonic_step_after": idx_state.get("step"),
            "total_activation":    idx_state.get("total_activation"),
            "neuro_k":             k_meta,
        })
        return result


@mcp.tool()
@requires_init
def cairrn_batch_run(
    metric: float = 1.0,
    semantic_matrix_value: float | None = None,
    partial_deriv_1: float | None = None,
    z_activation: float | None = None,
    z_energy_cost: float | None = None,
    z_uncertainty: float | None = None,
    rizomic_distance: float | None = None,
    sigma_accumulator: float | None = None,
    confidence: float | None = None,
    SHI: float | None = None,
    scope: float | None = None,
    pressure: float | None = None,
) -> dict[str, Any]:
    """
    Run the CAIRRN four-layer pipeline across ALL five station hubs simultaneously.

    Uses CAIRRNBatch to spin up one CAIRRNWorker per hub and feed them the same
    metric and optional inputs.  Returns per-hub results plus a batch shard summary.

    Parameters
    ----------
    metric : raw float metric shared by all hubs (default 1.0)
    (same optional Z-space / desktop formula params as cairrn_hub_run)
    """
    with _dom_queue.gate("cairrn_batch_run"):
        # Adaptive fill-in: same as cairrn_hub_run — caller override wins.
        eff_confidence  = confidence  if confidence  is not None else _adaptive_confidence()
        eff_energy_cost = z_energy_cost if z_energy_cost is not None else _adaptive_consumption()

        desktop_inputs = DesktopFormulaInputs(
            confidence=eff_confidence, SHI=SHI, scope=scope, pressure=pressure,
            energy_cost=eff_energy_cost, SCOP=scope,
            semantic_matrix_value=semantic_matrix_value,
            partial_deriv_1=partial_deriv_1,
            rizomic_distance=rizomic_distance,
            sigma_accumulator=sigma_accumulator,
            z_activation=z_activation,
            z_uncertainty=z_uncertainty,
        )

        batch = CAIRRNBatch(fn=lambda: metric, desktop_inputs=desktop_inputs)
        worker_results = batch.run_all()
        shard_summary = batch.summary()

        # Collect per-hub coherence values for the batch write-back.
        _batch_coherences: list[float] = []

        for _orig_hub, wr in worker_results.items():
            if wr.value and isinstance(wr.value, dict):
                cairrn_dict = wr.value.get("cairrn", {})
                effective = cairrn_dict.get("hub", _orig_hub)
                mod_val = cairrn_dict.get("modulated_metric", metric)
                _harmonic_index.inject_from_hub(effective, value=mod_val)
                if effective in _CAIRRN_HUBS:
                    _temporal_index.record(effective, value=mod_val)
                coh_val = cairrn_dict.get("coherence", {})
                if isinstance(coh_val, dict):
                    _batch_coherences.append(float(coh_val.get("coherence", 0.5)))
                elif isinstance(coh_val, (int, float)):
                    _batch_coherences.append(float(coh_val))

        # Write back mean coherence across all hubs as the adaptive confidence.
        if _batch_coherences:
            set_cairrn_coherence(sum(_batch_coherences) / len(_batch_coherences))

        # K attractor injection for batch — Tcv = mean coherence, hub = agent-context
        # (batch is session-level; agent-context shards carry session awareness).
        # propagate=False: propagation runs below.
        _batch_tcv = (sum(_batch_coherences) / len(_batch_coherences)) if _batch_coherences else 0.5
        k_meta_batch = _k_inject(_batch_tcv, hub_name="agent-context", propagate=False)

        _harmonic_index.propagate(steps=3, mode="local")
        idx_state = _harmonic_index.state()
        _vault_hub.push_harmonic(idx_state)

        hub_results: dict[str, Any] = {}
        for hub, wr in worker_results.items():
            if wr.value and isinstance(wr.value, dict):
                hub_results[hub] = wr.value.get("cairrn", {})
            else:
                hub_results[hub] = {"error": str(wr.error)}

        return {
            "metric":              metric,
            "n_hubs":              len(hub_results),
            "hubs":                hub_results,
            "shard_summary":       shard_summary,
            "neg_exp_fixed_point": _NEG_EXP_FIXED_POINT,
            "coherence_threshold": _CAIRRN_COHERENCE_THRESHOLD,
            "harmonic_step_after": idx_state.get("step"),
            "total_activation":    idx_state.get("total_activation"),
            "neuro_k":             k_meta_batch,
        }


@mcp.tool()
@requires_init
def cairrn_css_state() -> dict[str, Any]:
    """
    Read the live CSS (Coherence State Score) bitmask from the harmonic index.

    Computes a 6-bit bitmask over the middle shards (1–6) — each bit is 1 when
    that shard's activation exceeds the mean ring activation.  Matches the result
    against the known discrete CSS patterns and flags whether the ring is in the
    stable attractor state (101010: CODE+MATH+COMMANDS alternating).

    Returns
    -------
    bitmask          : 6-char binary string over shards 1–6
    hot_shards       : list of shard indices currently above mean
    stable_attractor : True when bitmask == "101010" (CSS locked)
    pattern_match    : label of the matching known pattern, or "unknown"
    shard_activations: all 8 raw shard activation values
    mean_activation  : mean of all 8 activations (bitmask threshold)
    m3_threshold     : current M3 gate threshold for reference
    """
    with _dom_queue.gate("cairrn_css_state"):
        if _harmonic_index is None:
            return {"error": "harmonic_index_unavailable"}

        activations = [s.activation for s in _harmonic_index.shards]
        mean_act = sum(activations) / max(len(activations), 1)

        # Bitmask over middle shards 1–6
        bits = "".join(
            "1" if activations[i] > mean_act else "0"
            for i in _CSS_MIDDLE_SHARDS
            if i < len(activations)
        )
        hot_shards = [i for i in _CSS_MIDDLE_SHARDS if i < len(activations) and activations[i] > mean_act]

        # Match against known patterns
        pattern_label = "unknown"
        for bitmask_str, hot_set, label in _CSS_PATTERNS:
            if frozenset(hot_shards) == hot_set:
                pattern_label = label
                break

        return {
            "bitmask":           bits,
            "hot_shards":        hot_shards,
            "stable_attractor":  bits == _CSS_STABLE_BITMASK,
            "pattern_match":     pattern_label,
            "shard_activations": [round(a, 6) for a in activations],
            "mean_activation":   round(mean_act, 6),
            "m3_threshold":      _M3_THRESHOLD,
        }


@mcp.tool()
@requires_init
def cairrn_m3_gate(
    pfs_score: float,
    n: int = 1,
    threshold: float | None = None,
) -> dict[str, Any]:
    """
    Evaluate the M3 prefeed quality gate against the live harmonic index.

    Computes CSS and M3 from the given PFS score and track count, using live
    shard activations as the proxy state (same path as _prefeed_shuffle_next).

    M3 = |CSS| · N · |PFS − SHI|
    CSS = f_css(proxy inputs derived from shard activations)

    A pending shuffle order PASSES when M3 ≤ threshold (low deviation = coherent).

    Parameters
    ----------
    pfs_score : mean harmonic resonance score of the pending shuffle order
                (FastFormula — output of PrefeedShuffle.prefeed())
    n         : track count from prefeed() (default 1)
    threshold : override the default M3_THRESHOLD (default None = use 1.0)

    Returns
    -------
    m3           : computed M3 quality composite
    css_proxy    : CSS value (proxy inputs; full formula requires session state)
    gate_passes  : True when m3 ≤ effective_threshold
    threshold    : effective threshold used
    shi          : Schema Health Index proxy (mean shard activation)
    pfs_score    : echo of input
    n            : echo of input
    """
    with _dom_queue.gate("cairrn_m3_gate"):
        if _harmonic_index is None:
            return {"error": "harmonic_index_unavailable"}

        activations = [s.activation for s in _harmonic_index.shards]
        m3 = _compute_m3(pfs_score, n, activations)
        shi = sum(activations) / max(len(activations), 1)
        effective_threshold = threshold if threshold is not None else _M3_THRESHOLD

        # CSS proxy for display: same inputs as _compute_m3 uses internally
        from workers.cairrn.formulas import f_css as _f_css
        from engine.cairrn_dispatch import _SHARD_MATH, _SHARD_MATH_SEC, _SHARD_CODE, _SHARD_COMMANDS
        ns = len(activations)
        e2 = activations[_SHARD_MATH]     if ns > _SHARD_MATH     else 0.0
        h2 = activations[_SHARD_MATH_SEC] ** 2 if ns > _SHARD_MATH_SEC else 0.0
        e1 = activations[_SHARD_CODE]     if ns > _SHARD_CODE     else 1.0
        e5 = activations[_SHARD_COMMANDS] if ns > _SHARD_COMMANDS else 0.0
        css_proxy = _f_css(
            a_nw=1.0, delta=pfs_score, cc=pfs_score,
            z_prev=1.0, z=1.0, tcv=1.0, scop=1.0,
            e2=e2, h2=h2, e5=e5, e1=e1,
        )

        return {
            "m3":                round(m3, 8),
            "css_proxy":         round(css_proxy, 8),
            "gate_passes":       m3 <= effective_threshold,
            "threshold":         effective_threshold,
            "shi":               round(shi, 6),
            "pfs_score":         pfs_score,
            "n":                 n,
            "shard_activations": [round(a, 6) for a in activations],
        }


@mcp.tool()
@requires_init
def cairrn_neuro_k(
    tracer_consensus_value: float,
    SHI: float | None = None,
    jules: float | None = None,
    jules_baseline: float = 0.0,
    drift: float | None = None,
    tracer_at_n: float | None = None,
    tip_value: float | None = None,
    inject: bool = False,
) -> dict[str, Any]:
    """
    Evaluate the neuro-activation K formula chain — F_TRACER_CONSENSUS_K,
    optionally F_JULES_NORM + F_DAWN_CONFIDENCE, optionally F_TICK_WISDOM.

    Pure formula evaluation.  No hub routing, no shard injection.

    Step 1 — F_TRACER_CONSENSUS_K  (always)
        K = |Tcv| − D     (D = SHI; live mean shard activation when not supplied)

    Step 2 — F_JULES_NORM + F_DAWN_CONFIDENCE  (when jules is given)
        j′ = round(jules, 3) − jules_baseline
        x  = |K · j′| ∨ drift    (∨ = max over magnitudes)

    Step 3 — F_TICK_WISDOM  (when tracer_at_n + tip_value are given)
        Tws = Tn / K   (0.0 when Tn < Tip)

    Parameters
    ----------
    tracer_consensus_value : Tcv — tracer consensus value
    SHI                    : D for step 1.  Defaults to live mean shard activation.
    jules                  : raw Jules energy value; triggers step 2.
    jules_baseline         : min(J_q) for F_JULES_NORM (default 0.0 — supply
                             the window minimum when normalising over a series).
    drift                  : D for F_DAWN_CONFIDENCE iwave.  Defaults to 0.0.
    tracer_at_n            : Tn — triggers step 3.
    tip_value              : Tip — minimum threshold for F_TICK_WISDOM.
    inject                 : when True, inject K·κ into the ring (agent-context hub).
    """
    with _dom_queue.gate("cairrn_neuro_k"):
        if SHI is None:
            if _harmonic_index is None:
                return {"error": "harmonic_index_unavailable", "hint": "supply SHI explicitly"}
            activations = [s.activation for s in _harmonic_index.shards]
            SHI = sum(activations) / max(len(activations), 1)
            shi_source = "live"
        else:
            shi_source = "caller"

        K = _f_tracer_consensus_k(tracer_consensus_value, SHI)

        result: dict[str, Any] = {
            "formula":  "F_TRACER_CONSENSUS_K",
            "expr":     "K = |Tcv| − D",
            "inputs":   {
                "Tcv":        tracer_consensus_value,
                "D_SHI":      round(SHI, 6),
                "SHI_source": shi_source,
            },
            "K": round(K, 8),
        }

        if jules is not None:
            j_q     = round(jules, 3)
            j_prime = j_q - jules_baseline
            D_dawn  = drift if drift is not None else 0.0
            x       = max(abs(K * j_prime), D_dawn)
            result["dawn_confidence"] = {
                "formula":        "F_DAWN_CONFIDENCE",
                "expr":           "x = |k · j′| ∨ D",
                "jules_raw":      jules,
                "J_q":            j_q,
                "jules_baseline": jules_baseline,
                "j_prime":        round(j_prime, 6),
                "D_drift":        D_dawn,
                "drift_source":   "caller" if drift is not None else "default_0",
                "x":              round(x, 8),
            }

        if tracer_at_n is not None and tip_value is not None:
            tws = _f_tick_wisdom(tracer_at_n, tip_value, K)
            result["tick_wisdom"] = {
                "formula": "F_TICK_WISDOM",
                "expr":    "Tws = Tn / K   (when Tn ≥ Tip)",
                "Tn":      tracer_at_n,
                "Tip":     tip_value,
                "K":       round(K, 8),
                "Tws":     round(tws, 8),
                "fired":   tracer_at_n >= tip_value,
            }

        if inject:
            result["neuro_k_inject"] = _k_inject(tracer_consensus_value, hub_name="agent-context")

        return result
