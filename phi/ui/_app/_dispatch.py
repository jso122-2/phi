# -*- coding: utf-8 -*-
"""phi.ui._app._dispatch — thread-safe scheduling, drain threads, and shutdown."""
from __future__ import annotations
import queue
import threading


_DRAIN_POLL_MS  = 16   # phi-poll drain interval (ms) — ~60 Hz, not 200 Hz
_DRAIN_DISP_MS  = 32   # phi-dispatch drain interval (ms)


class _DispatchMixin:
    """dispatch() / _sched() — queued callbacks; main-thread drain pumps; _on_close.

    Concrete subclasses must override _start_drain_threads() to install
    framework-specific QTimer drain pumps (see PhiMainWindow).
    """

    def _start_drain_threads(self) -> None:
        """Install drain pumps for _dispatch_queue and _poll_queue.

        Overridden by PhiMainWindow to use QTimer.  This base implementation
        exists only as a fallback and should not be reached in normal operation.
        """
        raise NotImplementedError("_start_drain_threads must be overridden by the Qt subclass")

    def dispatch(self, delay_ms: int, fn) -> None:
        """Thread-safe callback dispatcher for background threads.

        Queues fn in _dispatch_queue, drained on the main thread.
        delay_ms is accepted for API compatibility but is ignored — use _sched()
        when precise timing matters.
        """
        if getattr(self, "_closing", False):
            return
        self._dispatch_queue.put(fn)
        self._wake_drain("disp")

    def _sched(self, delay_ms: int, fn) -> None:
        """Thread-safe timer for time-critical callbacks (PollEngine, media keys, etc.).

        Routes fn to _poll_queue, drained on the main thread —
        separate from enrichment work in _dispatch_queue so slow jobs never
        delay playback ticks.
        """
        if getattr(self, "_closing", False):
            return
        if delay_ms <= 0:
            self._poll_queue.put(fn)
            self._wake_drain("poll")
        else:
            def _post() -> None:
                if getattr(self, "_closing", False):
                    return
                self._poll_queue.put(fn)
                self._wake_drain("poll")
            t = threading.Timer(delay_ms / 1000.0, _post)
            t.daemon = True
            t.start()

    def _wake_drain(self, which: str) -> None:
        """Restart a stopped drain timer. Qt subclass overrides; default is a no-op."""
        return

    def _on_close(self) -> None:
        """Hovercraft quit: hide → signal → persist → die. Never re-enter.

        Window death is owned by closeEvent. Do not call destroy()/close() here.
        """
        if getattr(self, "_closing", False):
            return
        self._closing = True

        poll = getattr(self, "poll_engine", None)
        if poll is not None:
            try:
                poll.stop()
            except Exception:
                pass
        self._drain_active = False
        for name in ("_disp_timer", "_poll_timer"):
            timer = getattr(self, name, None)
            if timer is not None:
                try:
                    timer.stop()
                except Exception:
                    pass

        hide = getattr(self, "hide", None)
        if callable(hide):
            try:
                hide()
            except Exception:
                pass

        player = getattr(self, "player", None)
        if player is not None:
            try:
                player.quit()
            except Exception:
                pass

        for name in (
            "enrich_daemon",
            "art_spider",
            "librosa_worker",
            "watcher",
            "media_keys",
        ):
            obj = getattr(self, name, None)
            if obj is not None and hasattr(obj, "stop"):
                try:
                    obj.stop()
                except Exception:
                    pass

        floor = getattr(self, "floor", None)
        if floor is not None:
            try:
                floor.shutdown(wait=False)
            except Exception:
                pass

        for meth in ("_save_session", "_flush_annotations"):
            fn = getattr(self, meth, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass

        curve = getattr(self, "curve_daemon", None)
        if curve is not None:
            try:
                curve.shutdown()
            except Exception:
                pass

        for name in ("meta_cache", "playlist_store"):
            obj = getattr(self, name, None)
            if obj is not None and hasattr(obj, "close"):
                try:
                    obj.close()
                except Exception:
                    pass

        # TODO: bound persist with a hard deadline if session save ever blocks.
        self._quit_app()

    def _quit_app(self) -> None:
        """Ask the Qt event loop to exit. Safe if Qt is not imported yet."""
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                app.quit()
        except Exception:
            pass
