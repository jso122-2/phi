# -*- coding: utf-8 -*-
"""Hovercraft quit: hide → signal → persist → die, with a re-entry guard."""
from __future__ import annotations

from unittest.mock import MagicMock

from phi.ui._app._dispatch import _DispatchMixin


class _DummyApp(_DispatchMixin):
    def __init__(self) -> None:
        self._closing = False
        self._drain_active = True
        self.hide_calls = 0
        self.destroy_calls = 0
        self.quit_calls = 0
        self.saved = 0
        self.flushed = 0
        self.poll_engine = MagicMock()
        self.enrich_daemon = MagicMock()
        self.art_spider = MagicMock()
        self.librosa_worker = MagicMock()
        self.watcher = MagicMock()
        self.media_keys = MagicMock()
        self.player = MagicMock()
        self.floor = MagicMock()
        self.curve_daemon = MagicMock()
        self.meta_cache = MagicMock()
        self.playlist_store = MagicMock()
        self.wakes: list[str] = []

    def _wake_drain(self, which: str) -> None:
        self.wakes.append(which)

    def hide(self) -> None:
        self.hide_calls += 1

    def destroy(self) -> None:
        self.destroy_calls += 1

    def _save_session(self) -> None:
        self.saved += 1

    def _flush_annotations(self) -> None:
        self.flushed += 1

    def _quit_app(self) -> None:
        self.quit_calls += 1


def test_on_close_hides_signals_persists_and_quits():
    app = _DummyApp()
    app._on_close()

    assert app._closing is True
    assert app._drain_active is False
    assert app.hide_calls == 1
    assert app.destroy_calls == 0
    assert app.quit_calls == 1
    assert app.saved == 1
    assert app.flushed == 1
    app.poll_engine.stop.assert_called_once()
    app.player.quit.assert_called_once()
    app.enrich_daemon.stop.assert_called_once()
    app.art_spider.stop.assert_called_once()
    app.librosa_worker.stop.assert_called_once()
    app.watcher.stop.assert_called_once()
    app.media_keys.stop.assert_called_once()
    app.floor.shutdown.assert_called_once_with(wait=False)
    app.curve_daemon.shutdown.assert_called_once()
    app.meta_cache.close.assert_called_once()
    app.playlist_store.close.assert_called_once()


def test_on_close_is_idempotent():
    app = _DummyApp()
    app._on_close()
    app._on_close()
    assert app.hide_calls == 1
    assert app.quit_calls == 1
    assert app.destroy_calls == 0
    app.player.quit.assert_called_once()


def test_sched_and_dispatch_noop_after_close():
    app = _DummyApp()
    app._poll_queue = __import__("queue").Queue()
    app._dispatch_queue = __import__("queue").Queue()
    app._on_close()
    app.dispatch(0, lambda: None)
    app._sched(0, lambda: None)
    assert app._dispatch_queue.empty()
    assert app._poll_queue.empty()


def test_dispatch_wakes_drain():
    app = _DummyApp()
    app._dispatch_queue = __import__("queue").Queue()
    app._poll_queue = __import__("queue").Queue()
    app.dispatch(0, lambda: None)
    app._sched(0, lambda: None)
    assert app.wakes == ["disp", "poll"]
