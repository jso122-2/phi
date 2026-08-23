# -*- coding: utf-8 -*-
"""phi.ui._app._session — session save/restore and annotation persistence."""
from __future__ import annotations
import os


class _SessionMixin:
    """Persist and restore playback state, queue, watch folder, and ML annotations."""

    def _save_session(self) -> None:
        self.session_mgr.save(
            self.library, self.queue, self.transport, self.watcher,
            self.smart_playlists, self.ranker_enabled, self.picker_enabled,
        )

    def _restore_session(self) -> None:
        data = self.session_mgr.load()
        if not data:
            return

        self.library.add(data.playlist)
        self.queue.shuffle_mode = data.shuffle_mode
        self.queue.repeat       = data.repeat
        if data.queue:
            self.queue.queue = data.queue
            self.queue.pos   = data.queue_pos
        else:
            self.queue.rebuild(self.library.size, keep_current=False)
            self.queue.pos = max(0, min(data.queue_pos, len(self.queue.queue) - 1))

        self.player.set_volume(data.volume)
        self.transport.set_volume(data.volume)
        self.transport.set_shuffle_mode(data.shuffle_mode)
        self.transport.set_repeat(data.repeat)
        self.transport.set_mode_label(data.shuffle_mode, data.repeat)

        # Restore arc engine state if session was in CAIRRN mode
        daemon = getattr(self, "curve_daemon", None)
        if daemon is not None:
            daemon.arc_engine.active = (data.shuffle_mode == "cairrn")
            if data.shuffle_mode == "cairrn":
                daemon.arc_engine.reset()

        if data.watch_folder and os.path.isdir(data.watch_folder):
            self.watcher.start(data.watch_folder, list(self.library.playlist))
            self.playlist_panel.set_watch(True, self.watcher.folder_name)

        if data.play_stats:
            self.library.play_stats.update(data.play_stats)

        self.ranker_enabled = data.ranker_enabled
        self.picker_enabled = data.picker_enabled

        from phi.core.smart_playlist import SmartPlaylist
        for pl_dict in data.smart_playlists:
            try:
                self.smart_playlists.append(SmartPlaylist.from_dict(pl_dict))
            except Exception:
                pass

        self.session_mgr.restore_annotations_bg(self.library, self.meta_cache)
        self._rebuild_view()

        if 0 <= self.queue.pos < len(self.queue.queue):
            pl_idx = self.queue.queue[self.queue.pos]
            path   = self.library.playlist[pl_idx]
            try:
                self.player.load(path)
                self.now_playing.set_title_only(path)
                self._async_meta(path)
                self._fetch_duration(path)
            except Exception:
                pass

        self._bg_meta(list(data.playlist))

    def _restore_annotations(self) -> None:
        self.session_mgr.restore_annotations_bg(self.library, self.meta_cache)

    def _flush_annotations(self) -> None:
        self.session_mgr.flush_annotations(self.library, self.meta_cache)
