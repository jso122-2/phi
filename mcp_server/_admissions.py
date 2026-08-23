"""
BMAD soft-defer admission predicates for DOM houses.

Each predicate is a zero-argument callable → bool. The gate polls it at 50 ms
intervals for up to 10 s; if the predicate doesn't clear, HouseAdmissionError
surfaces as a structured dict to the caller.

Safe-default: if the underlying singleton is None (failed init), the predicate
returns True so tooling is never permanently locked out.

Session-ledger integration
--------------------------
Predicates read from ``_session_ledger`` (the harmonic trajectory recorder) to
reflect *cumulative* session pressure, not just the instantaneous harmonic state.
This means BMAD tightens progressively as the agent drives CODE shards hard,
relaxes after a reset, and stays permissive at session open (no entries yet).
"""
from __future__ import annotations

import os

_CONSUMPTION_CAP: float = 2.0
"""CODE shards 3+4 combined cap for the modular house (instantaneous)."""

_CODE_PRESSURE_CAP: float = 4.0
"""Cumulative CODE delta cap from the session ledger for the modular house."""

_CONFIDENCE_FLOOR: float = 0.2
"""Minimum CAIRRN coherence for the wire (PSSPPS) house."""

_EDIT_CONFIDENCE_FLOOR: float = 0.5
"""Minimum confidence for the edit house; neutral (0.5, never-run) passes."""

_TEMPORAL_COHERENCE_FLOOR: float = 0.15
"""Minimum Ana-Chi coherence for the graph house (vault writes)."""

_TOTAL_PRESSURE_WARN: float = 8.0
"""Total session harmonic energy above which the graph house applies extra caution."""


def _ledger_code_pressure() -> float:
    """Read cumulative CODE-hub pressure from the session ledger (0.0 if unavailable)."""
    try:
        from mcp_server._state import _session_ledger
        return _session_ledger.code_pressure()
    except Exception:
        return 0.0


def _ledger_total_pressure() -> float:
    """Read cumulative total harmonic pressure from the session ledger."""
    try:
        from mcp_server._state import _session_ledger
        return _session_ledger.total_pressure()
    except Exception:
        return 0.0


def _predicate_modular() -> bool:
    """Modular house: block when CODE shards are overloaded (instantaneous OR session-cumulative)."""
    from mcp_server._state import _adaptive_consumption
    if _adaptive_consumption() >= _CONSUMPTION_CAP:
        return False
    # Also block if the session has been pushing CODE hard cumulatively.
    return _ledger_code_pressure() < _CODE_PRESSURE_CAP


def _predicate_wire() -> bool:
    """Wire house: require CAIRRN to have judged its own confidence."""
    from mcp_server._state import _adaptive_confidence
    return _adaptive_confidence() > _CONFIDENCE_FLOOR


def _predicate_edit() -> bool:
    """Edit house: CSS middle-band attractor stable OR sufficient confidence."""
    from mcp_server._state import _adaptive_confidence, _harmonic_index
    if _harmonic_index is None:
        return True
    shards = _harmonic_index.shards
    if len(shards) < 7:
        return True
    acts = [s.activation for s in shards]
    mean_act = sum(acts) / len(acts)
    css_stable = acts[1] > mean_act and acts[3] > mean_act and acts[5] > mean_act
    return css_stable or _adaptive_confidence() >= _EDIT_CONFIDENCE_FLOOR


def _predicate_graph() -> bool:
    """Graph house: require temporal coherence; also soften when session pressure is high."""
    from mcp_server._state import _temporal_index
    if _temporal_index is None:
        return True
    try:
        coherent = _temporal_index.ana_chi_coherence() > _TEMPORAL_COHERENCE_FLOOR
    except Exception:
        return True
    if not coherent:
        return False
    # Extra caution: if total session pressure is very high, require stronger coherence.
    if _ledger_total_pressure() > _TOTAL_PRESSURE_WARN:
        try:
            return _temporal_index.ana_chi_coherence() > _TEMPORAL_COHERENCE_FLOOR * 2
        except Exception:
            return True
    return True


def wire_admissions(dom_queue: object) -> None:
    """Attach admission predicates to the four soft-defer houses."""
    disable = os.environ.get("SPOTIFY_RIP_DISABLE_ADMISSION", "").strip().lower() in {
        "1", "true", "yes",
    }
    if disable:
        return
    for house_name, predicate in (
        ("modular", _predicate_modular),
        ("wire",    _predicate_wire),
        ("edit",    _predicate_edit),
        ("graph",   _predicate_graph),
    ):
        house = getattr(dom_queue, "_houses", {}).get(house_name)  # type: ignore[attr-defined]
        if house is not None:
            house._admission_check = predicate
