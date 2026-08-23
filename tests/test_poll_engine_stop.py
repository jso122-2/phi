# -*- coding: utf-8 -*-
"""PollEngine.stop() must make already-queued ticks no-ops."""
from __future__ import annotations

from unittest.mock import MagicMock

from phi.core.poll_engine import PollEngine


def _engine():
    scheduled = []

    def _schedule(_ms, fn):
        scheduled.append(fn)

    pe = PollEngine(
        player=MagicMock(),
        queue=MagicMock(),
        transport=MagicMock(),
        race_watcher=MagicMock(),
        beat=MagicMock(),
        hyphal=MagicMock(),
        floor=MagicMock(),
        media_keys=MagicMock(),
        schedule=_schedule,
        on_advance=MagicMock(),
        peek_next_path=MagicMock(return_value=None),
        get_duration=MagicMock(return_value=0.0),
        set_duration=MagicMock(),
    )
    return pe, scheduled


def test_start_schedules_first_tick():
    pe, scheduled = _engine()
    pe.start()
    assert pe._running is True
    assert scheduled == [pe._poll]


def test_stop_makes_queued_tick_a_noop():
    pe, scheduled = _engine()
    pe.start()
    scheduled.clear()
    pe.stop()
    pe._poll()
    assert pe._running is False
    assert scheduled == []
    pe._player.tick_state.assert_not_called()
