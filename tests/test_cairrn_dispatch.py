"""
Tests for engine/cairrn_dispatch.py — CAIRRN-bound action dispatcher.

Synthetic subsystems only — no disk I/O, no workers.cairrn calls.
"""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from engine.cairrn_dispatch import (
    CAIRRNDispatcher,
    DispatchResult,
    DoubleRouteEvent,
    DoubleRouteWatchdog,
    PhiAction,
    PhiActionKind,
    make_dispatcher,
)
from engine.gate import COHERENCE_THRESHOLD
from sims.harmonic import HarmonicIndex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_index(activations: list[float] | None = None) -> HarmonicIndex:
    idx = HarmonicIndex(n_harmonics=8, coupling=0.15)
    if activations:
        for i, v in enumerate(activations):
            idx.inject(i, v)
    return idx


def _make_dispatcher(
    activations: list[float] | None = None,
    tau: float = 10.0,
    threshold: float = COHERENCE_THRESHOLD,
) -> CAIRRNDispatcher:
    idx = _make_index(activations)
    return CAIRRNDispatcher(
        harmonic_index=idx,
        session=None,
        shuffle=None,
        temporal_index=None,
        tau=tau,
        threshold=threshold,
    )


def _action(kind: PhiActionKind, **payload) -> PhiAction:
    return PhiAction(kind=kind, payload=dict(payload))


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_defaults(self):
        d = _make_dispatcher()
        assert d._tau == 10.0
        assert d._threshold == pytest.approx(COHERENCE_THRESHOLD)
        assert d.queue_depth == 0
        assert d.ticks_run == 0

    def test_tau_clamped_positive(self):
        idx = _make_index()
        d = CAIRRNDispatcher(harmonic_index=idx, tau=0.0)
        assert d._tau > 0.0

    def test_factory(self):
        idx = _make_index()
        d = make_dispatcher(harmonic_index=idx)
        assert isinstance(d, CAIRRNDispatcher)


# ---------------------------------------------------------------------------
# PhiAction
# ---------------------------------------------------------------------------


class TestPhiAction:
    def test_all_kinds(self):
        for kind in PhiActionKind:
            a = PhiAction(kind=kind, payload={})
            assert a.kind == kind

    def test_unique_ids(self):
        ids = {PhiAction(kind=PhiActionKind.CLIP, payload={}).action_id for _ in range(50)}
        assert len(ids) == 50

    def test_as_dict(self):
        a = _action(PhiActionKind.HUB_INJECT, hub_name="CODE", value=0.5)
        d = a.as_dict()
        assert d["kind"] == "HUB_INJECT"
        assert d["payload"]["hub_name"] == "CODE"

    def test_priority_default_zero(self):
        a = PhiAction(kind=PhiActionKind.PROPAGATE, payload={})
        assert a.priority == 0


# ---------------------------------------------------------------------------
# Enqueue + priority ordering
# ---------------------------------------------------------------------------


class TestEnqueue:
    def test_enqueue_returns_depth(self):
        d = _make_dispatcher()
        depth = d.enqueue(_action(PhiActionKind.PROPAGATE))
        assert depth == 1
        depth = d.enqueue(_action(PhiActionKind.PROPAGATE))
        assert depth == 2

    def test_urgent_sorted_to_front(self):
        d = _make_dispatcher()
        normal = _action(PhiActionKind.PROPAGATE, steps=1)
        urgent = _action(PhiActionKind.SHARD_INJECT, shard_index=0, value=1.0)
        urgent.priority = -1
        d.enqueue(normal)
        d.enqueue(urgent)
        assert d._queue[0].action_id == urgent.action_id

    def test_deferred_sorted_to_back(self):
        d = _make_dispatcher()
        normal = _action(PhiActionKind.PROPAGATE, steps=1)
        deferred = _action(PhiActionKind.TEMPORAL_REC)
        deferred.priority = 1
        d.enqueue(deferred)
        d.enqueue(normal)
        assert d._queue[-1].action_id == deferred.action_id

    def test_fifo_within_same_priority(self):
        d = _make_dispatcher()
        a1 = _action(PhiActionKind.PROPAGATE)
        time.sleep(0.001)
        a2 = _action(PhiActionKind.PROPAGATE)
        d.enqueue(a1)
        d.enqueue(a2)
        assert d._queue[0].action_id == a1.action_id
        assert d._queue[1].action_id == a2.action_id


# ---------------------------------------------------------------------------
# Gate logic
# ---------------------------------------------------------------------------


class TestGate:
    def test_gate_closed_at_zero_steps(self):
        d = _make_dispatcher()
        assert d.gate_open is False
        assert d.coherence == pytest.approx(0.0)

    def test_gate_open_after_many_steps(self):
        d = _make_dispatcher()
        d._steps_since_tick = 100
        assert d.gate_open is True

    def test_step_gated_after_enough_steps(self):
        d = _make_dispatcher()
        d._steps_since_tick = 9   # 1 - exp(-0.9) ≈ 0.593 ≥ threshold → gate open
        with patch.object(d, "_run_cairrn_code_tick"):
            result = d.step()
        assert result.gated is True
        assert result.skipped is False

    def test_step_skipped_when_incoherent(self):
        d = _make_dispatcher()
        d._steps_since_tick = 6   # coherence < threshold with tau=10
        result = d.step()
        assert result.skipped is True
        assert result.gated is False

    def test_skip_increments_steps(self):
        d = _make_dispatcher()
        d._steps_since_tick = 6
        before = d.steps_since_tick
        d.step()
        assert d.steps_since_tick == before + 1

    def test_gate_open_resets_steps(self):
        d = _make_dispatcher()
        d._steps_since_tick = 9   # coherence ≈ 0.593 ≥ threshold → gate open
        with patch.object(d, "_run_cairrn_code_tick"):
            d.step()
        assert d.steps_since_tick == 0

    def test_ticks_run_increments_on_gate(self):
        d = _make_dispatcher()
        d._steps_since_tick = 9   # open gate
        with patch.object(d, "_run_cairrn_code_tick"):
            d.step()
        assert d.ticks_run == 1


# ---------------------------------------------------------------------------
# Action dispatch — built-in kinds (no workers.cairrn)
# ---------------------------------------------------------------------------


class TestDispatchActions:
    def test_shard_inject_dispatched(self):
        d = _make_dispatcher()
        d._steps_since_tick = 9   # gate open
        a = _action(PhiActionKind.SHARD_INJECT, shard_index=3, value=0.5)
        d.enqueue(a)
        with patch.object(d, "_run_cairrn_code_tick"):
            result = d.step()
        assert result.gated is True
        assert result.action.action_id == a.action_id
        assert result.result["injected_shard"] == 3

    def test_hub_inject_dispatched(self):
        d = _make_dispatcher()
        d._steps_since_tick = 9   # gate open
        a = _action(PhiActionKind.HUB_INJECT, hub_name="CODE", value=1.0)
        d.enqueue(a)
        with patch.object(d, "_run_cairrn_code_tick"):
            result = d.step()
        assert result.gated is True
        assert result.result["injected_hub"] == "CODE"

    def test_propagate_dispatched(self):
        d = _make_dispatcher()
        d._steps_since_tick = 9   # gate open
        a = _action(PhiActionKind.PROPAGATE, steps=2, mode="local")
        d.enqueue(a)
        with patch.object(d, "_run_cairrn_code_tick"):
            result = d.step()
        assert result.result["propagated"] is True
        assert result.result["steps"] == 2

    def test_empty_queue_still_gates(self):
        d = _make_dispatcher()
        d._steps_since_tick = 9   # gate open
        with patch.object(d, "_run_cairrn_code_tick"):
            result = d.step()
        assert result.gated is True
        assert result.action is None
        assert result.result is None

    def test_queue_drains_one_per_step(self):
        d = _make_dispatcher()
        d._steps_since_tick = 9   # gate open
        for _ in range(3):
            d.enqueue(_action(PhiActionKind.PROPAGATE, steps=1))
        with patch.object(d, "_run_cairrn_code_tick"):
            d.step()
        assert d.queue_depth == 2

    def test_temporal_rec_without_temporal_index(self):
        d = _make_dispatcher()
        d._steps_since_tick = 9   # gate open
        a = _action(PhiActionKind.TEMPORAL_REC, hub_name="CODE", value=0.5)
        d.enqueue(a)
        with patch.object(d, "_run_cairrn_code_tick"):
            result = d.step()
        assert "error" in result.result   # temporal_index_not_available

    def test_temporal_rec_with_index(self):
        mock_temporal = MagicMock()
        d = CAIRRNDispatcher(
            harmonic_index=_make_index(),
            temporal_index=mock_temporal,
        )
        d._steps_since_tick = 9   # gate open
        a = _action(PhiActionKind.TEMPORAL_REC, hub_name="CODE", value=0.7)
        d.enqueue(a)
        with patch.object(d, "_run_cairrn_code_tick"):
            result = d.step()
        mock_temporal.record.assert_called_once_with("CODE", 0.7)
        assert result.result["recorded_hub"] == "CODE"


# ---------------------------------------------------------------------------
# Prefeed
# ---------------------------------------------------------------------------


class TestPrefeed:
    def test_prefeed_runs_for_shuffle_next_when_gate_closed(self):
        mock_shuffle = MagicMock()
        mock_shuffle._session.snapshot = MagicMock()
        mock_shuffle._session.snapshot.N = 8
        d = CAIRRNDispatcher(harmonic_index=_make_index(), shuffle=mock_shuffle)
        d._steps_since_tick = 6   # gate closed
        a = _action(PhiActionKind.SHUFFLE_NEXT)
        d.enqueue(a)
        d.step()
        # prefeed_shuffle_next calls shuffle.shuffle.prefeed(snap, index)
        mock_shuffle.shuffle.prefeed.assert_called_once()

    def test_prefeed_not_repeated_for_same_action(self):
        mock_shuffle = MagicMock()
        mock_shuffle._session.snapshot = MagicMock()
        d = CAIRRNDispatcher(harmonic_index=_make_index(), shuffle=mock_shuffle)
        d._steps_since_tick = 6
        a = _action(PhiActionKind.SHUFFLE_NEXT)
        d.enqueue(a)
        # Mark as already prefeeded
        d._prefeed_cache[a.action_id] = "__prefeed_done__"
        d.step()   # gate closed but already cached → no second prefeed
        mock_shuffle.shuffle.prefeed.assert_not_called()

    def test_prefeed_cache_cleared_on_dispatch(self):
        d = _make_dispatcher()
        d._steps_since_tick = 9   # gate open so action executes and cache is cleared
        a = _action(PhiActionKind.SHARD_INJECT, shard_index=0, value=1.0)
        d.enqueue(a)
        d._prefeed_cache[a.action_id] = "fake_prefeed"
        with patch.object(d, "_run_cairrn_code_tick"):
            d.step()
        assert a.action_id not in d._prefeed_cache


class TestSkipCommitsPendingOrder:
    """force_dispatch(SHUFFLE_NEXT) must commit any pending CAIRRN order.

    When the user skips a track, force_dispatch() creates a brand-new
    PhiAction with a fresh action_id.  That id has no entry in the prefeed
    cache, so the old ``_prefeed_cache[action_id] == "__prefeed_done__"``
    check always misses.  The fix ensures that _exec_shuffle_next also
    commits when PrefeedShuffle._pending is non-empty — i.e. when a
    background prefeed() has already staged a CAIRRN-ordered list.
    """

    def _make_shuffle_mock(self, has_pending: bool = True) -> MagicMock:
        shuffle_inner = MagicMock()
        shuffle_inner.has_pending = has_pending
        shuffle_inner.commit.return_value = has_pending

        mock = MagicMock()
        mock.shuffle = shuffle_inner
        mock._session.snapshot.N = 4
        mock._session.snapshot.tracks = [MagicMock(name=f"T{i}", artist="") for i in range(4)]
        mock.next.return_value = 0
        return mock

    def test_force_dispatch_commits_pending_order(self):
        """Skip via force_dispatch commits the pending CAIRRN shuffle order."""
        mock_shuffle = self._make_shuffle_mock(has_pending=True)
        d = CAIRRNDispatcher(harmonic_index=_make_index(), shuffle=mock_shuffle)

        # Fresh action — no prefeed cache entry (simulates force_dispatch skip path)
        a = PhiAction(kind=PhiActionKind.SHUFFLE_NEXT, priority=-1)
        with patch.object(d, "_run_cairrn_code_tick"):
            d.force_dispatch(a)

        mock_shuffle.shuffle.commit.assert_called_once()

    def test_force_dispatch_no_commit_when_no_pending(self):
        """Skip with nothing in _pending does not call commit (safe no-op path)."""
        mock_shuffle = self._make_shuffle_mock(has_pending=False)
        d = CAIRRNDispatcher(harmonic_index=_make_index(), shuffle=mock_shuffle)

        a = PhiAction(kind=PhiActionKind.SHUFFLE_NEXT, priority=-1)
        with patch.object(d, "_run_cairrn_code_tick"):
            d.force_dispatch(a)

        mock_shuffle.shuffle.commit.assert_not_called()

    def test_gate_open_path_still_commits_via_cache(self):
        """Normal gate-open path still commits when prefeed cache entry is present."""
        mock_shuffle = self._make_shuffle_mock(has_pending=False)
        d = CAIRRNDispatcher(harmonic_index=_make_index(), shuffle=mock_shuffle)
        d._steps_since_tick = 9  # gate open

        a = PhiAction(kind=PhiActionKind.SHUFFLE_NEXT)
        d._prefeed_cache[a.action_id] = "__prefeed_done__"
        d.enqueue(a)
        with patch.object(d, "_run_cairrn_code_tick"):
            d.step()

        mock_shuffle.shuffle.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Force dispatch
# ---------------------------------------------------------------------------


class TestForceDispatch:
    def test_force_dispatch_bypasses_gate(self):
        d = _make_dispatcher()
        d._steps_since_tick = 100   # gate closed
        a = _action(PhiActionKind.SHARD_INJECT, shard_index=0, value=1.0)
        result = d.force_dispatch(a)
        assert result.gated is True
        assert result.result["injected_shard"] == 0

    def test_force_dispatch_does_not_reset_steps(self):
        d = _make_dispatcher()
        d._steps_since_tick = 5
        a = _action(PhiActionKind.PROPAGATE)
        d.force_dispatch(a)
        assert d.steps_since_tick == 5   # unchanged


# ---------------------------------------------------------------------------
# DispatchResult
# ---------------------------------------------------------------------------


class TestDispatchResult:
    def test_as_dict_gated(self):
        d = _make_dispatcher()
        d._steps_since_tick = 9   # gate open so action executes
        a = _action(PhiActionKind.PROPAGATE, steps=1)
        d.enqueue(a)
        with patch.object(d, "_run_cairrn_code_tick"):
            result = d.step()
        rd = result.as_dict()
        assert "gated" in rd
        assert "coherence" in rd
        assert "action" in rd

    def test_as_dict_skipped_no_action(self):
        d = _make_dispatcher()
        # steps=0 → coherence=0 < threshold → gate closed → skipped
        result = d.step()
        rd = result.as_dict()
        assert rd["skipped"] is True
        assert "action" not in rd

    def test_history_populated(self):
        d = _make_dispatcher()
        with patch.object(d, "_run_cairrn_code_tick"):
            d.step()
            d.step()
        hist = d.history_snapshot(5)
        assert len(hist) == 2


# ---------------------------------------------------------------------------
# State inspection
# ---------------------------------------------------------------------------


class TestState:
    def test_state_keys(self):
        d = _make_dispatcher()
        st = d.state()
        for key in ("coherence", "gate_open", "threshold", "tau",
                    "steps_since_tick", "ticks_run", "queue_depth",
                    "prefeed_cached", "code_activation", "queue"):
            assert key in st

    def test_queue_snapshot_empty(self):
        d = _make_dispatcher()
        assert d.queue_snapshot() == []

    def test_queue_snapshot_populated(self):
        d = _make_dispatcher()
        d.enqueue(_action(PhiActionKind.PROPAGATE, steps=2))
        snap = d.queue_snapshot()
        assert len(snap) == 1
        assert snap[0]["kind"] == "PROPAGATE"

    def test_repr(self):
        d = _make_dispatcher()
        r = repr(d)
        assert "coherence" in r
        assert "gate" in r
        assert "queue" in r


# ---------------------------------------------------------------------------
# DoubleRouteWatchdog
# ---------------------------------------------------------------------------


class TestDoubleRouteWatchdog:
    """Pericles-bound Euler watchdog — detects same-kind actions within window."""

    def _make_result(
        self,
        action: Optional[PhiAction] = None,
        coherence: float = 0.9,
        queue_depth: int = 1,
        steps_waiting: int = 1,
    ) -> DispatchResult:
        return DispatchResult(
            gated=True, skipped=False,
            coherence=coherence, code_act=0.5,
            steps_waiting=steps_waiting,
            action=action, result=None,
            prefeed_was_ready=False, prefeeding=False,
            queue_depth=queue_depth,
        )

    def test_no_event_on_first_observe(self):
        d = _make_dispatcher()
        wd = DoubleRouteWatchdog(d, window_ms=450.0)
        a = _action(PhiActionKind.SHUFFLE_NEXT)
        result = self._make_result(action=a)
        wd.observe(result)
        assert wd.state()["total_events"] == 0

    def test_no_event_when_none_action(self):
        d = _make_dispatcher()
        wd = DoubleRouteWatchdog(d, window_ms=450.0)
        result = self._make_result(action=None)
        wd.observe(result)
        wd.observe(result)
        assert wd.state()["total_events"] == 0

    def test_double_route_detected_within_window(self):
        d = _make_dispatcher()
        wd = DoubleRouteWatchdog(d, window_ms=450.0)
        a = _action(PhiActionKind.SHUFFLE_NEXT)
        result = self._make_result(action=a, coherence=0.3)

        wd.observe(result)
        time.sleep(0.01)   # 10ms apart — well within 450ms window
        wd.observe(result)

        state = wd.state()
        assert state["total_events"] == 1
        event = state["recent"][0]
        assert event["kind"] == "SHUFFLE_NEXT"
        assert event["dt_ms"] < 450.0
        assert "per" in event

    def test_no_double_route_outside_window(self):
        d = _make_dispatcher()
        wd = DoubleRouteWatchdog(d, window_ms=5.0)   # tiny 5ms window
        a = _action(PhiActionKind.SHUFFLE_NEXT)
        result = self._make_result(action=a)

        wd.observe(result)
        time.sleep(0.010)   # 10ms > 5ms window
        wd.observe(result)

        assert wd.state()["total_events"] == 0

    def test_different_kinds_no_cross_contamination(self):
        d = _make_dispatcher()
        wd = DoubleRouteWatchdog(d, window_ms=450.0)
        r_next = self._make_result(action=_action(PhiActionKind.SHUFFLE_NEXT))
        r_seed = self._make_result(action=_action(PhiActionKind.SHUFFLE_SEED))

        wd.observe(r_next)
        wd.observe(r_seed)   # different kind — not a double-route
        assert wd.state()["total_events"] == 0

    def test_euler_bound_flag_below_threshold(self):
        """euler_bound=True when coherence < W(1) ≈ 0.5671."""
        from engine.gate import COHERENCE_THRESHOLD
        d = _make_dispatcher()
        wd = DoubleRouteWatchdog(d, window_ms=450.0)
        a = _action(PhiActionKind.SHUFFLE_NEXT)
        result = self._make_result(action=a, coherence=COHERENCE_THRESHOLD - 0.1)

        wd.observe(result)
        wd.observe(result)

        event = wd.state()["recent"][0]
        assert event["euler_bound"] is True

    def test_euler_bound_false_above_threshold(self):
        from engine.gate import COHERENCE_THRESHOLD
        d = _make_dispatcher()
        wd = DoubleRouteWatchdog(d, window_ms=450.0)
        a = _action(PhiActionKind.SHUFFLE_NEXT)
        result = self._make_result(action=a, coherence=COHERENCE_THRESHOLD + 0.1)

        wd.observe(result)
        wd.observe(result)

        event = wd.state()["recent"][0]
        assert event["euler_bound"] is False

    def test_pericles_score_present_and_positive(self):
        d = _make_dispatcher()
        wd = DoubleRouteWatchdog(d, window_ms=450.0)
        a = _action(PhiActionKind.SHUFFLE_NEXT)
        result = self._make_result(action=a, coherence=0.8, queue_depth=2, steps_waiting=3)

        wd.observe(result)
        time.sleep(0.005)
        wd.observe(result)

        event = wd.state()["recent"][0]
        assert event["per"] >= 0.0
        assert event["x"] > 0.0

    def test_clear_resets_state(self):
        d = _make_dispatcher()
        wd = DoubleRouteWatchdog(d, window_ms=450.0)
        a = _action(PhiActionKind.SHUFFLE_NEXT)
        result = self._make_result(action=a)

        wd.observe(result)
        wd.observe(result)
        assert wd.state()["total_events"] == 1

        wd.clear()
        assert wd.state()["total_events"] == 0
        # After clear, next observe is treated as first-seen — no event
        wd.observe(result)
        assert wd.state()["total_events"] == 0

    def test_attach_and_integrate_with_dispatcher(self):
        """Watchdog wired into dispatcher detects double-route from force_dispatch."""
        d = _make_dispatcher()
        wd = DoubleRouteWatchdog(d, window_ms=450.0)
        d.attach_double_route_watchdog(wd)

        a = _action(PhiActionKind.SHARD_INJECT, shard_index=0, value=1.0)
        d.force_dispatch(a)
        d.force_dispatch(a)

        assert wd.state()["total_events"] == 1

    def test_euler_bound_count_in_state(self):
        from engine.gate import COHERENCE_THRESHOLD
        d = _make_dispatcher()
        wd = DoubleRouteWatchdog(d, window_ms=450.0)
        a = _action(PhiActionKind.SHUFFLE_NEXT)

        # Euler-bound event (coherence < W(1))
        r_low = self._make_result(action=a, coherence=COHERENCE_THRESHOLD - 0.1)
        wd.observe(r_low)
        wd.observe(r_low)

        state = wd.state()
        assert state["euler_bound_count"] == 1
        assert state["total_events"] == 1
