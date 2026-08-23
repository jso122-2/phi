# -*- coding: utf-8 -*-
"""Skip (on_next) must stop at end of queue when repeat is off."""
from __future__ import annotations

from unittest.mock import MagicMock

from phi.core.queue import QueueEngine
from phi.ui._app._transport import _TransportMixin


class _SkipHost(_TransportMixin):
    def __init__(self, queue: QueueEngine) -> None:
        self.queue = queue
        self.library = MagicMock()
        self.library.playlist = []
        self.player = MagicMock()
        self.transport = MagicMock()
        self.curve_daemon = None
        self._load_and_play = MagicMock()
        self._last_next_at = 0.0


def test_next_user_none_at_end_without_repeat():
    q = QueueEngine()
    q.queue = [0, 1, 2]
    q.pos = 2
    q.repeat = "off"
    assert q.next_user() is None


def test_next_user_wraps_when_repeat_all():
    q = QueueEngine()
    q.queue = [0, 1, 2]
    q.pos = 2
    q.repeat = "all"
    assert q.next_user() == 0


def test_on_next_loads_next_track():
    q = QueueEngine()
    q.queue = [0, 1, 2]
    q.pos = 0
    host = _SkipHost(q)
    host.on_next()
    host._load_and_play.assert_called_once_with(1)
    host.player.stop.assert_not_called()


def test_on_next_stops_at_end_of_queue():
    q = QueueEngine()
    q.queue = [0, 1, 2]
    q.pos = 2
    q.repeat = "off"
    host = _SkipHost(q)
    host.on_next()
    host._load_and_play.assert_not_called()
    host.player.stop.assert_called_once()
    host.transport.set_playing.assert_called_once_with(False)
