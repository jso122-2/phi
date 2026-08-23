# -*- coding: utf-8 -*-
"""phi.ui._app._window — window utilities, UI refresh, status flash, room sync."""
from __future__ import annotations
import os
import threading

from phi.config import WATCH_POLL_MS

_REFRESH_DEBOUNCE_MS = 150   # coalesce rapid meta-ready bursts into one list rebuild


class _WindowMixin:
    """Fullscreen, sleep timer, settings, mini player, seek/vol helpers, flash, refresh."""

    def _rebuild_view(self, search: str | None = None) -> None:
        if search is None:
            search = self.playlist_panel.search_var.get()
        names = self.library.all_display_names_by_queue(self.queue.queue)
        self.queue.apply_search(search, names)
        self._refresh_playlist()

    def _refresh_playlist(self) -> None:
        self.playlist_panel.refresh(
            self.queue.queue,
            self.queue.view,
            self.queue.pos,
            self.library,
        )
        if self.queue.queue:
            self.sidebar.update_queue(
                self.queue.queue,
                self.queue.pos,
                self.library,
            )
        # Keep the queue room in sync whenever the queue mutates
        _qr = getattr(self, "_queue_page", None)
        if _qr is not None and hasattr(_qr, "refresh_queue"):
            _qr.refresh_queue()

    # ── debounced refresh ─────────────────────────────────────────────────────

    def _schedule_refresh(self) -> None:
        """Debounce rapid _refresh_playlist calls into one update per 150 ms.

        During library loading, _on_meta_ready fires for every track in
        sequence.  Each call would otherwise trigger a full list-widget rebuild
        + sidebar queue update (O(n) SQLite reads).  Coalescing them means the
        UI rebuilds at most once per _REFRESH_DEBOUNCE_MS interval instead of
        hundreds of times per second.
        """
        if getattr(self, "_refresh_pending", False):
            return
        self._refresh_pending = True
        self._sched(_REFRESH_DEBOUNCE_MS, self._flush_refresh)

    def _flush_refresh(self) -> None:
        self._refresh_pending = False
        self._refresh_playlist()

    def _flash(self, msg: str, ms: int = 3_000) -> None:
        self.playlist_panel.flash_status(msg)
        watch_name = self.watcher.folder_name if self.watcher.active else ""
        self._sched(ms, lambda: self.playlist_panel.flash_status(
            f"W {watch_name}" if watch_name else ""
        ))

    def _poll_rooms_transport(self, playing: bool) -> None:
        """Keep the mini transport bar in Library / Playlist / Mixer / ML rooms in sync."""
        if not self._in_rooms:
            return

        current_playlist_idx = self.queue.current_playlist_idx
        if current_playlist_idx >= 0 and current_playlist_idx < len(self.library.playlist):
            cur_path = self.library.playlist[current_playlist_idx]
            meta     = self.library.get_meta(cur_path) or {}
            title    = meta.get("title") or os.path.splitext(os.path.basename(cur_path))[0]
            artist   = meta.get("artist") or ""
        else:
            cur_path = title = artist = ""

        pos = self.player.position() if self.duration > 0 else 0.0

        if self._in_ml_table:
            active_page = self._ml_page_frames.get(self._ml_page_names[self._ml_page_idx])
        else:
            active_page = self._page_frames.get(self._page_names[self._page_idx])
        if active_page and hasattr(active_page, "sync_transport"):
            active_page.sync_transport(title, artist, playing, pos, self.duration)

    def _watch_poll(self) -> None:
        if self.watcher.active:
            threading.Thread(target=self._do_watch_scan, daemon=True, name="watch-scan").start()
        self._sched(WATCH_POLL_MS, self._watch_poll)

    def _do_watch_scan(self) -> None:
        new = self.watcher.scan()  # os.listdir — safe to call from any thread
        if new:
            self._sched(0, lambda n=new: self._on_new_watch_files(n))

    def _on_new_watch_files(self, new: list[str]) -> None:
        self.library.add(new)
        self.queue.rebuild(self.library.size, keep_current=True)
        self._rebuild_view()

    def _on_sleep_tick(self, remaining: int | None) -> None:
        """Update the status strip with the sleep countdown."""
        if remaining is None:
            self.playlist_panel.flash_status("")
        else:
            m, s = remaining // 60, remaining % 60
            self.playlist_panel.flash_status(f"⏾ {m}:{s:02d}")

    def _seek_rel(self, delta: float) -> None:
        if self.duration <= 0:
            return
        cur = self.player.position()
        self.player.seek(max(0.0, min(self.duration, cur + delta)), self.duration)

    def _seek_start(self) -> None:
        if self.duration > 0:
            self.player.seek(0.0, self.duration)

    def _vol_step(self, delta: float) -> None:
        v = max(0.0, min(1.0, self.transport._vol_var.get() + delta))
        self.on_volume(v)
