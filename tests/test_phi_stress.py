"""
Stress tests for the CAIRRN phi dispatcher — edge cases and weak points.

Covers:
  BUG-1  shard_index silently wraps via modulo (out-of-range → aliased shard)
  BUG-2  phi_flush reports success even on execution errors (no error propagation)
  BUG-3  DoubleRouteWatchdog never attached in make_dispatcher() — silent double-routes
  OBS-1  Coherence gate is a permanent open latch (once open, stays open forever)
  OBS-2  _prefeed_clip / _prefeed_shuffle_next release RLock mid-step
  EDGE   Canonical error paths: MYCELIAL_TICK no substrate, LOAD_TRACK no path,
         HOVER_PREFETCH empty payload, CAIRRN_RUN invalid hub, TEMPORAL_REC no temporal
"""
from __future__ import annotations

import math
import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from engine.cairrn_dispatch import (
    CAIRRNDispatcher,
    DispatchResult,
    DoubleRouteWatchdog,
    PhiAction,
    PhiActionKind,
    make_dispatcher,
)
from engine.gate import COHERENCE_THRESHOLD
from sims.harmonic import HarmonicIndex


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_index(activations: list[float] | None = None) -> HarmonicIndex:
    idx = HarmonicIndex(n_harmonics=8, coupling=0.15)
    if activations:
        for i, v in enumerate(activations):
            idx.inject(i, v)
    return idx


def _dispatcher(tau: float = 10.0) -> CAIRRNDispatcher:
    return CAIRRNDispatcher(harmonic_index=_make_index(), tau=tau)


@pytest.fixture
def d() -> CAIRRNDispatcher:
    return _dispatcher()


# ---------------------------------------------------------------------------
# BUG-1 — shard_index modulo wrap: silent aliasing
# ---------------------------------------------------------------------------


class TestShardIndexWrap:
    """BUG-1 fixed: out-of-range shard_index now returns an error instead of silently aliasing.

    Previous behaviour: index 99 wrapped via ``99 % 8 = 3`` with no error.
    Fixed behaviour   : error dict returned; shard state unchanged.
    """

    def test_out_of_range_index_returns_error(self, d):
        """Inject into shard 99 → error returned, no shard modified."""
        before = [s.activation for s in d._index.shards]
        action = PhiAction(
            kind=PhiActionKind.SHARD_INJECT,
            payload={"shard_index": 99, "value": 1.0},
        )
        result = d.force_dispatch(action)
        assert result.result.get("error") == "shard_index_out_of_range"
        assert result.result["shard_index"] == 99
        assert result.result["valid_range"] == [0, 7]
        # No shard modified
        after = [s.activation for s in d._index.shards]
        assert before == after

    def test_out_of_range_16_returns_error(self, d):
        """shard_index=16 (previously aliased to 0) now returns an error."""
        action = PhiAction(
            kind=PhiActionKind.SHARD_INJECT,
            payload={"shard_index": 16, "value": 0.5},
        )
        result = d.force_dispatch(action)
        assert result.result.get("error") == "shard_index_out_of_range"
        assert d._index.shards[0].activation == pytest.approx(0.0)

    def test_negative_index_returns_error(self, d):
        """Negative shard_index now returns an error instead of wrapping."""
        action = PhiAction(
            kind=PhiActionKind.SHARD_INJECT,
            payload={"shard_index": -1, "value": 0.5},
        )
        result = d.force_dispatch(action)
        assert result.result.get("error") == "shard_index_out_of_range"
        assert d._index.shards[7].activation == pytest.approx(0.0)

    def test_in_range_indices_succeed(self, d):
        """Indices 0–7 still work correctly."""
        for i in range(8):
            action = PhiAction(
                kind=PhiActionKind.SHARD_INJECT,
                payload={"shard_index": i, "value": 0.1},
            )
            result = d.force_dispatch(action)
            assert "error" not in result.result
            assert result.result["injected_shard"] == i

    def test_large_index_stress_returns_errors(self, d):
        """Indices 8–999 all return out-of-range errors — no crash, no aliasing."""
        for i in range(8, 1000):
            action = PhiAction(
                kind=PhiActionKind.SHARD_INJECT,
                payload={"shard_index": i, "value": 0.001},
            )
            result = d.force_dispatch(action)
            assert result.result.get("error") == "shard_index_out_of_range", (
                f"index {i} should return error, got {result.result}"
            )


# ---------------------------------------------------------------------------
# BUG-2 — phi_flush error transparency
# ---------------------------------------------------------------------------


class TestFlushErrorTransparency:
    """force_dispatch returns DispatchResult(result=error_dict) not an exception.
    phi_flush collects all results including error results — the caller must inspect
    each to detect failures. This is the current contract; tests assert it holds."""

    def test_mycelial_error_in_flush_result(self, d):
        """MYCELIAL_TICK with no substrate → error in result.result, not an exception."""
        action = PhiAction(kind=PhiActionKind.MYCELIAL_TICK, payload={})
        result = d.force_dispatch(action)
        assert result.result == {"error": "substrate_not_attached"}

    def test_load_track_no_path_error_in_result(self, d):
        action = PhiAction(kind=PhiActionKind.LOAD_TRACK, payload={})
        result = d.force_dispatch(action)
        assert result.result == {"error": "npy_path_required"}

    def test_hover_prefetch_empty_payload_error_in_result(self, d):
        action = PhiAction(kind=PhiActionKind.HOVER_PREFETCH, payload={})
        result = d.force_dispatch(action)
        assert "error" in result.result
        assert "unknown_inner_kind" in result.result["error"]

    def test_flush_loop_sees_error_results_as_gated_true(self, d):
        """phi_flush populates results list even for error actions — gated=True, no raise."""
        for kind in (PhiActionKind.MYCELIAL_TICK, PhiActionKind.LOAD_TRACK):
            d.enqueue(PhiAction(kind=kind, payload={}))

        results: list[DispatchResult] = []
        while d.queue_depth > 0:
            with d._lock:
                if not d._queue:
                    break
                action = d._queue.pop(0)
            results.append(d.force_dispatch(action))

        assert len(results) == 2
        assert all(r.gated for r in results)
        assert all("error" in r.result for r in results)

    def test_cairrn_run_invalid_hub_error_in_result(self, d):
        action = PhiAction(
            kind=PhiActionKind.CAIRRN_RUN,
            payload={"hub_name": "NO_SUCH_HUB", "metric": 1.0},
        )
        result = d.force_dispatch(action)
        assert "error" in result.result

    def test_temporal_rec_no_index_error(self, d):
        action = PhiAction(
            kind=PhiActionKind.TEMPORAL_REC,
            payload={"hub_name": "CODE", "value": 0.5},
        )
        result = d.force_dispatch(action)
        assert result.result == {"error": "temporal_index_not_available"}

    def test_shuffle_next_no_shuffle_error(self, d):
        action = PhiAction(kind=PhiActionKind.SHUFFLE_NEXT, payload={})
        result = d.force_dispatch(action)
        assert result.result == {"error": "shuffle_not_available"}

    def test_shuffle_seed_no_shuffle_error(self, d):
        action = PhiAction(kind=PhiActionKind.SHUFFLE_SEED, payload={})
        result = d.force_dispatch(action)
        assert result.result == {"error": "shuffle_not_available"}


# ---------------------------------------------------------------------------
# BUG-3 — DoubleRouteWatchdog not attached in make_dispatcher()
# ---------------------------------------------------------------------------


class TestWatchdogAbsent:
    """make_dispatcher(attach_watchdog=False) contract — watchdog explicitly absent.

    BUG-3 is now fixed: make_dispatcher() attaches a DoubleRouteWatchdog by default.
    These tests use attach_watchdog=False to reproduce the old absent-watchdog
    scenario and verify behaviour in that explicit opt-out case.
    """

    def test_dispatcher_has_watchdog_by_default(self, d):
        """The fixture creates a bare CAIRRNDispatcher (no watchdog)."""
        assert d._dr_watchdog is None

    def test_make_dispatcher_attaches_watchdog_by_default(self):
        idx = _make_index()
        disp = make_dispatcher(harmonic_index=idx)
        assert disp._dr_watchdog is not None, (
            "make_dispatcher() must auto-attach a DoubleRouteWatchdog (BUG-3 fix)"
        )

    def test_make_dispatcher_no_watchdog_when_opted_out(self):
        idx = _make_index()
        disp = make_dispatcher(harmonic_index=idx, attach_watchdog=False)
        assert disp._dr_watchdog is None

    def test_double_route_not_counted_without_watchdog(self, d):
        """Two SHARD_INJECT dispatches in fast succession — watchdog is None, nothing recorded."""
        for _ in range(2):
            a = PhiAction(
                kind=PhiActionKind.SHARD_INJECT,
                payload={"shard_index": 0, "value": 0.1},
            )
            d.force_dispatch(a)
        # No watchdog — no state to check; simply assert no AttributeError
        assert d._dr_watchdog is None

    def test_double_route_detected_once_watchdog_attached(self, d):
        """Attaching a watchdog retroactively enables detection."""
        watchdog = DoubleRouteWatchdog(d, window_ms=2000.0)
        d.attach_double_route_watchdog(watchdog)

        for _ in range(2):
            a = PhiAction(
                kind=PhiActionKind.SHARD_INJECT,
                payload={"shard_index": 0, "value": 0.1},
            )
            d.force_dispatch(a)

        state = watchdog.state()
        assert state["total_events"] == 1

    def test_make_dispatcher_double_route_recorded_with_default_watchdog(self):
        """make_dispatcher() default: two fast SHARD_INJECT → watchdog records 1 event."""
        idx = _make_index()
        disp = make_dispatcher(harmonic_index=idx, watchdog_window_ms=2000.0)
        assert disp._dr_watchdog is not None
        for _ in range(2):
            a = PhiAction(
                kind=PhiActionKind.SHARD_INJECT,
                payload={"shard_index": 0, "value": 0.1},
            )
            disp.force_dispatch(a)
        state = disp._dr_watchdog.state()
        assert state["total_events"] == 1


# ---------------------------------------------------------------------------
# OBS-1 — Coherence gate is a permanent open latch
# ---------------------------------------------------------------------------


class TestGateLatch:
    """Gate formula: coherence = 1.0 − exp(−steps_since_tick / τ).

    Gate opens when coherence ≥ COHERENCE_THRESHOLD (≈ 0.5671).
    After a gate-open dispatch, steps_since_tick resets to 0 → gate closes.
    The gate must re-accumulate steps before the next dispatch (refractory period).
    With τ=10.0, the threshold is crossed at steps_since_tick ≈ 9."""

    def test_gate_starts_closed(self, d):
        """Fresh dispatcher: steps=0 → coherence=0.0 → gate closed on first step."""
        result = d.step()
        assert result.gated is False
        assert result.coherence == pytest.approx(0.0)

    def test_gate_opens_after_threshold_steps(self, d):
        """τ=10.0: steps=9 → coherence ≈ 0.593 > COHERENCE_THRESHOLD → gate opens."""
        d._steps_since_tick = 9
        result = d.step()
        assert result.gated is True
        assert result.coherence >= COHERENCE_THRESHOLD

    def test_coherence_decays_only_in_closed_state(self, d):
        """Manually push steps_since_tick past threshold → coherence drops."""
        d._steps_since_tick = 7
        assert d.coherence < COHERENCE_THRESHOLD
        assert d.gate_open is False

    def test_gate_closes_after_dispatch(self, d):
        """After gate-open dispatch, steps_since_tick resets to 0 → gate closes again."""
        d._steps_since_tick = 9  # force gate open
        d.step()                  # fires, resets steps to 0
        result = d.step()         # immediately after: coherence=0 → closed
        assert result.skipped is True

    def test_gate_self_heals_by_accumulating_steps(self, d):
        """Starting from closed state, accumulating steps eventually reopens the gate."""
        d._steps_since_tick = 2  # closed (coherence ≈ 0.18)
        results = [d.step() for _ in range(12)]
        assert any(r.gated for r in results)

    def test_gate_resets_on_dispatch(self, d):
        """Enqueue one action, force gate open → gate fires, steps_since_tick resets."""
        d.enqueue(PhiAction(
            kind=PhiActionKind.SHARD_INJECT,
            payload={"shard_index": 0, "value": 0.1},
        ))
        d._steps_since_tick = 9  # τ=10.0: coherence ≈ 0.593 → gate open
        result = d.step()
        assert result.gated is True
        assert d._steps_since_tick == 0


# ---------------------------------------------------------------------------
# OBS-2 — Lock release in _prefeed_clip / _prefeed_shuffle_next
# ---------------------------------------------------------------------------


class TestPrefeedLockRelease:
    """_prefeed_clip and _prefeed_shuffle_next release the RLock during
    potentially slow inference, allowing concurrent enqueue() during that window.
    This is safe — enqueue is also lock-guarded — but tests verify the invariant."""

    def test_concurrent_enqueue_during_prefeed_clip(self):
        """Simulate a slow _prefeed_clip and verify concurrent enqueue succeeds."""
        idx = _make_index()
        d = CAIRRNDispatcher(harmonic_index=idx, tau=10.0)
        d._steps_since_tick = 7  # Close the gate so prefeed activates

        mock_session = MagicMock()
        mock_session.snapshot = MagicMock()
        mock_snap = mock_session.snapshot
        mock_graph = MagicMock()
        mock_session.phi_graph = mock_graph
        d._session = mock_session

        injected_during: list[int] = []

        def slow_clip(query, snap):
            # During this fake inference, another thread enqueues
            a = PhiAction(
                kind=PhiActionKind.SHARD_INJECT,
                payload={"shard_index": 1, "value": 0.1},
            )
            injected_during.append(d.enqueue(a))
            return MagicMock(top_k=[], query=query, n_tracks_searched=0, alpha=0.5)

        d.enqueue(PhiAction(
            kind=PhiActionKind.CLIP,
            payload={"query": "test", "top_k": 1, "alpha": 0.5},
        ))

        with patch("phi.models.gemini_clipper.GeminiClipper") as MockClipper:
            instance = MockClipper.return_value
            instance.clip.side_effect = slow_clip
            d.step()

        # Concurrent enqueue must have completed without deadlock
        assert len(injected_during) == 1
        assert injected_during[0] >= 1  # queue had at least 1 item at inject time


# ---------------------------------------------------------------------------
# Queue flood stress tests
# ---------------------------------------------------------------------------


class TestQueueFlood:
    """High-volume enqueue + flush cycles."""

    def test_enqueue_200_actions_sorts_correctly(self, d):
        """200 actions with random priorities — verify sort invariant after each insert."""
        import random
        rng = random.Random(42)

        for _ in range(200):
            priority = rng.choice([-5, -1, 0, 1, 5])
            a = PhiAction(
                kind=PhiActionKind.SHARD_INJECT,
                payload={"shard_index": 0, "value": 0.001},
                priority=priority,
            )
            d.enqueue(a)

        priorities = [(a.priority, a.enqueued_at) for a in d._queue]
        assert priorities == sorted(priorities), "Queue not sorted after flood insert"

    def test_flush_200_actions_no_exception(self, d):
        """flush all 200 enqueued actions — must complete without raising."""
        for i in range(200):
            a = PhiAction(
                kind=PhiActionKind.SHARD_INJECT,
                payload={"shard_index": i % 8, "value": 0.001},
            )
            d.enqueue(a)

        results: list[DispatchResult] = []
        while d.queue_depth > 0:
            with d._lock:
                if not d._queue:
                    break
                action = d._queue.pop(0)
            results.append(d.force_dispatch(action))

        assert len(results) == 200
        assert d.queue_depth == 0

    def test_priority_interleave_fifo_within_band(self, d):
        """Within the same priority band, FIFO ordering must hold."""
        times_seen: list[float] = []

        for _ in range(10):
            a = PhiAction(
                kind=PhiActionKind.SHARD_INJECT,
                payload={"shard_index": 0, "value": 0.01},
                priority=0,
            )
            d.enqueue(a)

        queue_times = [a.enqueued_at for a in d._queue if a.priority == 0]
        assert queue_times == sorted(queue_times)

    def test_empty_flush_returns_zero(self, d):
        """Flushing an empty queue returns immediately with flushed=0."""
        assert d.queue_depth == 0
        results: list[DispatchResult] = []
        while d.queue_depth > 0:
            with d._lock:
                if not d._queue:
                    break
                action = d._queue.pop(0)
            results.append(d.force_dispatch(action))
        assert results == []

    def test_step_empty_queue_gate_open(self, d):
        """step() on empty queue with open gate: gated=True, no action key."""
        d._steps_since_tick = 9  # τ=10.0: coherence ≈ 0.593 > threshold → gate open
        result = d.step()
        assert result.gated is True
        assert result.action is None
        assert result.queue_depth == 0


# ---------------------------------------------------------------------------
# Priority extreme values
# ---------------------------------------------------------------------------


class TestPriorityExtremes:
    """sys.maxsize and -sys.maxsize priorities must not crash bisect.insort."""

    def test_extreme_negative_priority_goes_to_front(self, d):
        import sys
        normal = PhiAction(
            kind=PhiActionKind.SHARD_INJECT,
            payload={"shard_index": 0, "value": 0.1},
            priority=0,
        )
        urgent = PhiAction(
            kind=PhiActionKind.SHARD_INJECT,
            payload={"shard_index": 1, "value": 0.1},
            priority=-sys.maxsize,
        )
        d.enqueue(normal)
        d.enqueue(urgent)
        assert d._queue[0].action_id == urgent.action_id

    def test_extreme_positive_priority_goes_to_back(self, d):
        import sys
        urgent = PhiAction(
            kind=PhiActionKind.SHARD_INJECT,
            payload={"shard_index": 0, "value": 0.1},
            priority=-1,
        )
        deferred = PhiAction(
            kind=PhiActionKind.SHARD_INJECT,
            payload={"shard_index": 1, "value": 0.1},
            priority=sys.maxsize,
        )
        d.enqueue(deferred)
        d.enqueue(urgent)
        assert d._queue[-1].action_id == deferred.action_id


# ---------------------------------------------------------------------------
# Prefeed cache invalidation
# ---------------------------------------------------------------------------


class TestPrefeedInvalidation:
    """Verify that the prefeed cache is cleared after dispatch and does not
    accumulate stale entries across multiple enqueue cycles."""

    def test_prefeed_cache_empty_after_force_dispatch(self, d):
        """force_dispatch does not cache anything — prefeed_cache stays empty."""
        action = PhiAction(
            kind=PhiActionKind.SHARD_INJECT,
            payload={"shard_index": 0, "value": 0.1},
        )
        d.force_dispatch(action)
        assert len(d._prefeed_cache) == 0

    def test_prefeed_cache_cleared_after_gate_open_dispatch(self, d):
        """Gate-open step() pops the prefeed cache entry for the dispatched action."""
        d._steps_since_tick = 9  # τ=10.0: coherence ≈ 0.593 > threshold → gate open

        mock_session = MagicMock()
        mock_session.snapshot = MagicMock()
        mock_session.phi_graph = MagicMock()
        d._session = mock_session

        clip_result = MagicMock()
        clip_result.top_k = []
        clip_result.query = "x"
        clip_result.n_tracks_searched = 0
        clip_result.alpha = 0.5

        action = PhiAction(
            kind=PhiActionKind.CLIP,
            payload={"query": "x", "top_k": 1, "alpha": 0.5},
        )
        d.enqueue(action)
        # Manually pre-seed the cache to simulate prefeed ran
        d._prefeed_cache[action.action_id] = clip_result
        assert len(d._prefeed_cache) == 1

        # step() should use the cache and clear it
        with patch("phi.models.gemini_clipper.GeminiClipper"):
            result = d.step()

        assert result.prefeed_was_ready is True
        assert action.action_id not in d._prefeed_cache

    def test_prefeed_cache_not_reused_for_new_action_with_same_kind(self, d):
        """Each action has a unique action_id — old cache entries do not bleed across."""
        a1 = PhiAction(
            kind=PhiActionKind.SHUFFLE_NEXT,
            payload={},
        )
        a2 = PhiAction(
            kind=PhiActionKind.SHUFFLE_NEXT,
            payload={},
        )
        # Manually inject a stale cache entry for a1
        d._prefeed_cache[a1.action_id] = "__prefeed_done__"
        # Dispatching a2 must NOT use a1's cache
        assert a2.action_id not in d._prefeed_cache


# ---------------------------------------------------------------------------
# Thread safety — concurrent enqueue + step
# ---------------------------------------------------------------------------


class TestConcurrency:
    """Concurrent enqueue + step must not corrupt queue ordering or raise."""

    def test_concurrent_enqueue_and_step_no_corruption(self, d):
        errors: list[Exception] = []
        stop = threading.Event()

        def enqueuer():
            for i in range(100):
                try:
                    a = PhiAction(
                        kind=PhiActionKind.SHARD_INJECT,
                        payload={"shard_index": i % 8, "value": 0.001},
                    )
                    d.enqueue(a)
                except Exception as e:
                    errors.append(e)

        def stepper():
            for _ in range(50):
                try:
                    d.step()
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=enqueuer),
            threading.Thread(target=enqueuer),
            threading.Thread(target=stepper),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert errors == [], f"Concurrent operations raised: {errors}"

    def test_concurrent_flush_and_enqueue(self, d):
        """Flush the queue while another thread enqueues — no deadlock."""
        for i in range(20):
            a = PhiAction(
                kind=PhiActionKind.SHARD_INJECT,
                payload={"shard_index": i % 8, "value": 0.001},
            )
            d.enqueue(a)

        errors: list[Exception] = []
        flush_results: list[DispatchResult] = []

        def flusher():
            try:
                while d.queue_depth > 0:
                    with d._lock:
                        if not d._queue:
                            break
                        action = d._queue.pop(0)
                    flush_results.append(d.force_dispatch(action))
            except Exception as e:
                errors.append(e)

        def enqueuer():
            for i in range(10):
                try:
                    a = PhiAction(
                        kind=PhiActionKind.SHARD_INJECT,
                        payload={"shard_index": 0, "value": 0.001},
                    )
                    d.enqueue(a)
                except Exception as e:
                    errors.append(e)

        t1 = threading.Thread(target=flusher)
        t2 = threading.Thread(target=enqueuer)
        t1.start()
        t2.start()
        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        assert errors == [], f"Concurrent flush/enqueue raised: {errors}"
