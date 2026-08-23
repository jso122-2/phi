"""
Tests for CAIRRNScheduler — engine/cairrn_scheduler.py.

Synthetic PhiTracerSession (no disk I/O).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from engine.cairrn_scheduler import CAIRRNScheduler, SchedulerResult, make_cairrn_scheduler
from engine.gate import COHERENCE_THRESHOLD
from engine.phi_session import PhiTracerSession
from engine.tracer_daemon import TracerDaemon, TracerSummary
from phi.graph.phi_graph import PhiGraph, PhiGraphSnapshot
from phi.library import Track


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_summary(**kwargs) -> TracerSummary:
    defaults = dict(
        n_tracers=1, arm_prune=0.1, arm_graft=0.1, arm_cluster=0.1,
        arm_rank=0.1, arm_tag=0.1, arm_resurface=0.1, arm_merge=0.1,
        arm_sprout=0.1, aggregated_tag=0.1, aggregated_merge=0.1,
        mean_tick=1.0, mean_coherence=0.9, mean_ana_chi_weight=0.98,
    )
    defaults.update(kwargs)
    return TracerSummary(**defaults)


def _make_snap(N: int = 4, d: int = 256, seed: int = 0) -> PhiGraphSnapshot:
    rng = np.random.default_rng(seed)
    H = rng.standard_normal((N, d))
    norms = np.linalg.norm(H, axis=1, keepdims=True)
    H = H / np.where(norms < 1e-12, 1e-12, norms)
    A = np.zeros((N, N))
    tracks = [
        Track(path=Path(f"/fake/T{i}.mp3"), json_path=Path(f"/fake/T{i}.json"))
        for i in range(N)
    ]
    return PhiGraphSnapshot(tracks=tracks, H=H, A=A)


def _make_session_mock(summary: TracerSummary | None = None) -> PhiTracerSession:
    """Session mock with tick() and refresh_and_tick() returning *summary*."""
    if summary is None:
        summary = _make_summary()
    snap = _make_snap()
    mock_graph = MagicMock(spec=PhiGraph)
    mock_graph.build.return_value = snap

    daemon = TracerDaemon(max_tracers=2, tick_gate_interval=4, d=256, coherence_tau=10.0)
    session = PhiTracerSession(phi_graph=mock_graph, daemon=daemon)
    session.build()

    # Patch tick() and refresh_and_tick() so tests control what they return.
    session.tick = MagicMock(return_value=summary)
    session.refresh_and_tick = MagicMock(return_value=summary)
    return session


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_defaults(self):
        session = _make_session_mock()
        s = CAIRRNScheduler(session)
        assert s.steps_since_tick == 0
        assert s.ticks_run == 0
        assert s._tau == 10.0
        assert s._threshold == pytest.approx(COHERENCE_THRESHOLD, abs=1e-9)
        assert s._refresh_every == 0

    def test_custom_params(self):
        session = _make_session_mock()
        s = CAIRRNScheduler(session, tau=5.0, threshold=0.3, refresh_every=3)
        assert s._tau == 5.0
        assert s._threshold == pytest.approx(0.3)
        assert s._refresh_every == 3

    def test_tau_clamped_to_positive(self):
        session = _make_session_mock()
        s = CAIRRNScheduler(session, tau=0.0)
        assert s._tau > 0.0


# ---------------------------------------------------------------------------
# Gate logic
# ---------------------------------------------------------------------------


class TestGate:
    def test_first_step_coherence_is_zero_gate_closed(self):
        """steps_since_tick=0 → coherence=0.0 → gate closed → prefeed, no tick."""
        session = _make_session_mock()
        s = CAIRRNScheduler(session, tau=10.0, threshold=COHERENCE_THRESHOLD)
        result = s.step()
        assert result.gated is False
        assert result.skipped is True
        assert result.coherence == pytest.approx(0.0)

    def test_gate_blocked_when_incoherent(self):
        """Force steps_since_tick high enough that coherence < threshold."""
        session = _make_session_mock()
        # threshold ≈ 0.5671 → need coherence < 0.5671
        # exp(-steps/tau) < 0.5671 when steps > tau * W(1) ≈ 10 * 0.567 ≈ 5.67
        # So steps_since_tick = 6 with tau=10 → coherence ≈ 0.549 < 0.5671 → blocked
        s = CAIRRNScheduler(session, tau=10.0, threshold=COHERENCE_THRESHOLD)
        s._steps_since_tick = 6
        result = s.step()
        assert result.skipped is True
        assert result.gated is False
        assert result.summary is None

    def test_skipped_increments_steps(self):
        session = _make_session_mock()
        s = CAIRRNScheduler(session, tau=10.0, threshold=COHERENCE_THRESHOLD)
        s._steps_since_tick = 6   # gate closed
        before = s.steps_since_tick
        s.step()
        assert s.steps_since_tick == before + 1

    def test_gated_tick_resets_steps(self):
        session = _make_session_mock()
        s = CAIRRNScheduler(session)
        # 1 - exp(-9/10) ≈ 0.593 ≥ 0.5671 → gate open
        s._steps_since_tick = 9
        result = s.step()
        assert result.gated is True
        assert s.steps_since_tick == 0

    def test_gated_increments_ticks_run(self):
        session = _make_session_mock()
        s = CAIRRNScheduler(session)
        s._steps_since_tick = 9   # open gate for first tick
        s.step()
        assert s.ticks_run == 1
        s._steps_since_tick = 9   # gate reset to 0 after tick — reopen for second
        s.step()
        assert s.ticks_run == 2


# ---------------------------------------------------------------------------
# Tick vs refresh dispatch
# ---------------------------------------------------------------------------


class TestDispatch:
    def test_plain_tick_by_default(self):
        session = _make_session_mock()
        s = CAIRRNScheduler(session, refresh_every=0)
        s._steps_since_tick = 9   # gate open
        s.step()
        session.tick.assert_called_once()
        session.refresh_and_tick.assert_not_called()

    def test_force_refresh_triggers_refresh_and_tick(self):
        session = _make_session_mock()
        s = CAIRRNScheduler(session)
        s._steps_since_tick = 9   # gate open
        result = s.step(force_refresh=True)
        session.refresh_and_tick.assert_called_once()
        session.tick.assert_not_called()
        assert result.refresh_ran is True

    def test_auto_refresh_at_interval(self):
        """refresh_every=2 → refresh on 3rd tick (ticks_run=2 before that call)."""
        session = _make_session_mock()
        s = CAIRRNScheduler(session, refresh_every=2)

        s._steps_since_tick = 9
        s.step()  # tick 1 — plain tick
        session.tick.assert_called_once()
        session.refresh_and_tick.assert_not_called()

        # After tick 1: ticks_run=1, steps reset to 0.
        # tick 2: ticks_run=1, 1 % 2 != 0 → plain tick → ticks_run=2
        s._steps_since_tick = 9
        s.step()

        # tick 3: ticks_run=2 before call; 2 % 2 == 0 → auto-refresh
        s._steps_since_tick = 9
        s.step()
        assert session.refresh_and_tick.call_count == 1

    def test_no_refresh_ran_on_plain_tick(self):
        session = _make_session_mock()
        s = CAIRRNScheduler(session, refresh_every=0)
        result = s.step()
        assert result.refresh_ran is False


# ---------------------------------------------------------------------------
# force_tick
# ---------------------------------------------------------------------------


class TestForceTick:
    def test_force_tick_bypasses_gate(self):
        session = _make_session_mock()
        s = CAIRRNScheduler(session, tau=10.0, threshold=COHERENCE_THRESHOLD)
        s._steps_since_tick = 100  # coherence ≈ 0 → gate closed
        result = s.force_tick()
        assert result.gated is True
        assert result.skipped is False
        session.tick.assert_called_once()

    def test_force_tick_with_refresh(self):
        session = _make_session_mock()
        s = CAIRRNScheduler(session)
        result = s.force_tick(refresh=True)
        session.refresh_and_tick.assert_called_once()
        assert result.refresh_ran is True

    def test_force_tick_resets_steps(self):
        session = _make_session_mock()
        s = CAIRRNScheduler(session)
        s._steps_since_tick = 50
        s.force_tick()
        assert s.steps_since_tick == 0


# ---------------------------------------------------------------------------
# SchedulerResult
# ---------------------------------------------------------------------------


class TestSchedulerResult:
    def test_result_fields_present(self):
        session = _make_session_mock()
        s = CAIRRNScheduler(session)
        result = s.step()
        assert hasattr(result, "gated")
        assert hasattr(result, "skipped")
        assert hasattr(result, "coherence")
        assert hasattr(result, "code_activation")
        assert hasattr(result, "steps_since_tick")
        assert hasattr(result, "refresh_ran")
        assert hasattr(result, "summary")

    def test_as_dict_gated(self):
        session = _make_session_mock()
        s = CAIRRNScheduler(session)
        s._steps_since_tick = 9   # gate open
        result = s.step()
        d = result.as_dict()
        assert d["gated"] is True
        assert "summary" in d

    def test_as_dict_skipped_no_summary(self):
        session = _make_session_mock()
        s = CAIRRNScheduler(session, threshold=COHERENCE_THRESHOLD)
        # steps=0 → coherence=0 < threshold → gate closed
        result = s.step()
        d = result.as_dict()
        assert d["gated"] is False
        assert "summary" not in d


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class TestState:
    def test_state_dict_keys(self):
        session = _make_session_mock()
        s = CAIRRNScheduler(session)
        st = s.state()
        for key in ("steps_since_tick", "ticks_run", "coherence", "threshold",
                    "tau", "refresh_every", "code_activation", "gate_open"):
            assert key in st

    def test_gate_closed_after_reset(self):
        """reset_steps() sets steps=0 → coherence=0 → gate CLOSED (cooldown begins)."""
        session = _make_session_mock()
        s = CAIRRNScheduler(session)
        s._steps_since_tick = 100   # coherence ≈ 1.0 → gate OPEN
        assert s.coherence >= COHERENCE_THRESHOLD
        s.reset_steps()
        assert s.coherence == pytest.approx(0.0)
        assert s.state()["gate_open"] is False

    def test_repr_contains_coherence(self):
        session = _make_session_mock()
        s = CAIRRNScheduler(session)
        assert "coherence" in repr(s)
        assert "gate" in repr(s)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestFactory:
    def test_make_cairrn_scheduler_returns_instance(self):
        session = _make_session_mock()
        s = make_cairrn_scheduler(session, tau=5.0, refresh_every=2)
        assert isinstance(s, CAIRRNScheduler)
        assert s._tau == 5.0
        assert s._refresh_every == 2
