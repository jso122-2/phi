# -*- coding: utf-8 -*-
"""tests/test_cairn_tick.py — CairnTick unit tests.

Focus: dispatcher.step() must fire even when the player is idle
(duration=0 / raw_ms=-1).  The heartbeat must NOT fire when idle.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, call

import pytest

from phi.core._poll_cairrn import CairnTick
from phi.core._poll_state import TickSnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snap(duration: float = 3.0, raw_ms: int = 500) -> TickSnapshot:
    """Active-playback snapshot."""
    pos = raw_ms / 1000.0
    return TickSnapshot(
        busy=True,
        raw_ms=raw_ms,
        pos=pos,
        duration=duration,
        paused=False,
        playing=True,
        energy=0.5,
        on_beat=False,
    )


def _idle_snap() -> TickSnapshot:
    """Idle / no-track snapshot (player stopped between tracks)."""
    return TickSnapshot(
        busy=False,
        raw_ms=-1,
        pos=0.0,
        duration=0.0,
        paused=False,
        playing=False,
        energy=0.0,
        on_beat=False,
    )


def _advance(tick: CairnTick, snap: TickSnapshot, n: int) -> None:
    """Drive the tick counter forward by n ticks, waiting for threads to settle."""
    for _ in range(n):
        tick.tick(snap)
    # Allow background daemon thread to finish
    time.sleep(0.05)


# ---------------------------------------------------------------------------
# Counter / rate-limiting
# ---------------------------------------------------------------------------

class TestCounter:
    def test_does_not_fire_before_every(self):
        floor = MagicMock()
        dispatcher = MagicMock()
        t = CairnTick(floor, dispatcher, every=5)
        for _ in range(4):
            t.tick(_snap())
        time.sleep(0.02)
        floor.heartbeat.assert_not_called()
        dispatcher.step.assert_not_called()

    def test_fires_at_every(self):
        floor = MagicMock()
        dispatcher = MagicMock()
        t = CairnTick(floor, dispatcher, every=5)
        _advance(t, _snap(), 5)
        floor.heartbeat.assert_called_once()
        dispatcher.step.assert_called_once()

    def test_counter_resets_after_fire(self):
        floor = MagicMock()
        dispatcher = MagicMock()
        t = CairnTick(floor, dispatcher, every=3)
        _advance(t, _snap(), 6)  # two full windows
        assert dispatcher.step.call_count == 2


# ---------------------------------------------------------------------------
# Core fix: dispatcher.step() fires even when idle
# ---------------------------------------------------------------------------

class TestIdleDispatch:
    def test_dispatcher_step_fires_when_idle(self):
        """dispatcher.step() must fire even when duration=0 / raw_ms=-1."""
        floor = MagicMock()
        dispatcher = MagicMock()
        t = CairnTick(floor, dispatcher, every=3)

        _advance(t, _idle_snap(), 3)

        dispatcher.step.assert_called_once()

    def test_heartbeat_does_not_fire_when_idle(self):
        """floor.heartbeat() must NOT fire when there is no active track."""
        floor = MagicMock()
        dispatcher = MagicMock()
        t = CairnTick(floor, dispatcher, every=3)

        _advance(t, _idle_snap(), 3)

        floor.heartbeat.assert_not_called()

    def test_dispatcher_step_fires_across_idle_boundary(self):
        """Steps accrue through an idle period — simulates track-to-track gap."""
        floor = MagicMock()
        dispatcher = MagicMock()
        t = CairnTick(floor, dispatcher, every=3)

        _advance(t, _snap(), 3)      # first window: playing
        _advance(t, _idle_snap(), 3) # second window: idle between tracks
        _advance(t, _snap(), 3)      # third window: playing again

        assert dispatcher.step.call_count == 3

    def test_heartbeat_fires_only_during_playback(self):
        """heartbeat fires in playing windows but not in idle window."""
        floor = MagicMock()
        dispatcher = MagicMock()
        t = CairnTick(floor, dispatcher, every=3)

        _advance(t, _snap(), 3)      # playing
        _advance(t, _idle_snap(), 3) # idle
        _advance(t, _snap(), 3)      # playing

        assert floor.heartbeat.call_count == 2


# ---------------------------------------------------------------------------
# Running guard — backlog prevention
# ---------------------------------------------------------------------------

class TestRunningGuard:
    def test_second_fire_skipped_while_running(self):
        """If the daemon thread is still running, the next eligible tick skips."""
        floor = MagicMock()
        dispatcher = MagicMock()

        barrier = threading.Event()

        def slow_step():
            barrier.wait(timeout=2.0)

        dispatcher.step.side_effect = slow_step

        t = CairnTick(floor, dispatcher, every=1)

        # First tick — launches thread, which blocks on barrier
        t.tick(_snap())
        time.sleep(0.02)
        assert t._running is True

        # Second tick — should be skipped
        t.tick(_snap())
        time.sleep(0.02)
        assert dispatcher.step.call_count == 1  # still only one call

        barrier.set()  # unblock the thread
        time.sleep(0.05)
        assert t._running is False


# ---------------------------------------------------------------------------
# No dispatcher — floor-only mode
# ---------------------------------------------------------------------------

class TestNoDispatcher:
    def test_no_error_when_dispatcher_is_none(self):
        floor = MagicMock()
        t = CairnTick(floor, dispatcher=None, every=3)
        _advance(t, _snap(), 3)
        floor.heartbeat.assert_called_once()

    def test_idle_no_dispatcher_no_error(self):
        floor = MagicMock()
        t = CairnTick(floor, dispatcher=None, every=3)
        _advance(t, _idle_snap(), 3)
        floor.heartbeat.assert_not_called()
