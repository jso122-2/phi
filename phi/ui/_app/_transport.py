# -*- coding: utf-8 -*-
"""phi.ui._app._transport — playback transport callbacks."""
from __future__ import annotations

import time

# Matches the DoubleRouteWatchdog window used in the pygame frontend.
# Prevents a rapid double-click (or click + key repeat reaching here before
# the key-layer guard fires) from calling load_and_play twice in a row.
_NEXT_PREV_DEBOUNCE_S = 0.45


class _TransportMixin:
    """Play/pause, seek, volume, shuffle, repeat — all transport control."""

    def on_play_pause(self) -> None:
        if self._picker:
            self._picker.close()
            self._picker = None
            nxt = self.queue.advance()
            if nxt is not None:
                self._load_and_play(nxt)
            else:
                self.player.stop()
                self.transport.set_playing(False)
            return

        if not self.queue.queue:
            if self.library.size == 0:
                return
            self.queue.rebuild(self.library.size, keep_current=False)
            self._rebuild_view()
        if self.queue.pos < 0:
            self._load_and_play(0)
            return
        if self.player.is_busy():
            self.player.pause()
            self.transport.set_playing(False)
            self.media_keys.set_playback_state(self.player.position(), False)
        elif self.player.paused:
            self.player.unpause()
            self.transport.set_playing(True)
            self.media_keys.set_playback_state(self.player.position(), True)
        elif self.player.loaded_path:
            self.player.play()
            self.transport.set_playing(True)
            self.media_keys.set_playback_state(0.0, True)
        else:
            self._load_and_play(self.queue.pos)

    def on_prev(self) -> None:
        now = time.monotonic()
        if now - getattr(self, "_last_prev_at", 0.0) < _NEXT_PREV_DEBOUNCE_S:
            return
        self._last_prev_at = now
        if not self.player.loaded_path:
            self._load_and_play(self.queue.pos)
            return
        for _ in range(3):
            node = self.playback.history.back()
            if node is None:
                break
            pl = node.playlist_idx
            if 0 <= pl < len(self.library.playlist) and self.library.playlist[pl] == node.path:
                try:
                    qpos = self.queue.queue.index(pl)
                    self._load_and_play(qpos)
                    return
                except ValueError:
                    pass
        prev = self.queue.prev()
        if prev is None:
            self.player.seek(0.0, self.duration)
            self.transport.reset_seek()
        else:
            self._load_and_play(prev)

    def on_next(self) -> None:
        now = time.monotonic()
        if now - getattr(self, "_last_next_at", 0.0) < _NEXT_PREV_DEBOUNCE_S:
            return
        self._last_next_at = now

        # In CAIRRN mode the arc engine drives next-track selection via a
        # pre-queued slot at pos+1.  Refresh it now so a manual skip always
        # lands on an arc-picked track, not just the next sequential position.
        if self.queue.shuffle_mode == "cairrn":
            daemon = getattr(self, "curve_daemon", None)
            if daemon is not None:
                cur_idx = self.queue.current_playlist_idx
                if 0 <= cur_idx < len(self.library.playlist):
                    daemon.suggest_next_for(self.library.playlist[cur_idx])

        nxt = self.queue.next_user()
        if nxt is not None:
            self._load_and_play(nxt)
        else:
            # Last track, repeat off: skip must stop, not sit on a silent channel.
            self.player.stop()
            self.transport.set_playing(False)

    def on_stop(self) -> None:
        self.player.stop()
        self.transport.set_playing(False)
        self.transport.reset_seek()

    def on_seek(self, seconds: float) -> None:
        if self.duration > 0 and (self.player.is_busy() or self.player.paused):
            self.player.seek(seconds, self.duration)

    def on_volume(self, v: float) -> None:
        if getattr(self.player, "muted", False):
            self.player.set_muted(False)
        self.player.set_volume(v)
        self.transport.set_volume(v)

    def _apply_replaygain(self, meta: dict) -> None:
        """Scale playback volume by the track's ReplayGain gain tag."""
        from phi.ui.settings_dialog import load_settings
        if not load_settings().get("replaygain", True):
            return
        gain_db = meta.get("rg_track_gain")
        if gain_db is None:
            return
        try:
            scale = 10 ** (float(gain_db) / 20.0)
        except (TypeError, ValueError):
            return
        base = self.transport._vol_var.get()
        adjusted = max(0.0, min(1.0, base * scale))
        self.player.set_volume(adjusted)

    def on_toggle_mute(self) -> None:
        """Toggle mute: silence output, restore prior slider level on unmute."""
        if not self.player.muted:
            self._vol_before_mute = self.transport._vol_var.get()
            self.player.set_muted(True)
            self.transport.set_volume(0.0)
        else:
            self.player.set_muted(False)
            self.on_volume(getattr(self, "_vol_before_mute", 0.7))

    def on_toggle_shuffle(self) -> None:
        mode = self.queue.cycle_shuffle(self.library.size)
        self._rebuild_view()

        # CAIRRN mode: activate the arc engine so it drives next-track selection
        daemon = getattr(self, "curve_daemon", None)
        if daemon is not None:
            daemon.arc_engine.active = (mode == "cairrn")
            if mode == "cairrn":
                daemon.arc_engine.reset()
                daemon._recent_paths.clear()
                # Pre-queue the very first arc suggestion immediately.
                # on_track_change already fired for the playing track *before*
                # this toggle, so nothing is at pos+1 yet — without this call
                # the first advance() after enabling CAIRRN always plays
                # sequentially.
                cur_idx = self.queue.current_playlist_idx
                if 0 <= cur_idx < len(self.library.playlist):
                    daemon.suggest_next_for(self.library.playlist[cur_idx])

        self.transport.set_shuffle_mode(mode)
        self.transport.set_mode_label(mode, self.queue.repeat)

    def on_cycle_repeat(self) -> None:
        self.queue.cycle_repeat()
        self.transport.set_repeat(self.queue.repeat)
        self.transport.set_mode_label(self.queue.shuffle_mode, self.queue.repeat)
