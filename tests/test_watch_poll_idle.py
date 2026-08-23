# -*- coding: utf-8 -*-
"""Folder watcher poll must not spawn a thread when inactive."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from phi.ui._app._window import _WindowMixin


class _Dummy(_WindowMixin):
    def __init__(self, active: bool) -> None:
        self.watcher = MagicMock()
        self.watcher.active = active
        self.scheduled = []

    def _sched(self, delay_ms, fn) -> None:
        self.scheduled.append((delay_ms, fn))

    def _do_watch_scan(self) -> None:
        raise AssertionError("scan must not run on the dummy")


def test_watch_poll_skips_thread_when_inactive():
    app = _Dummy(active=False)
    with patch("phi.ui._app._window.threading.Thread") as thread_cls:
        app._watch_poll()
        thread_cls.assert_not_called()
    assert len(app.scheduled) == 1


def test_watch_poll_starts_thread_when_active():
    app = _Dummy(active=True)
    with patch("phi.ui._app._window.threading.Thread") as thread_cls:
        app._watch_poll()
        thread_cls.assert_called_once()
