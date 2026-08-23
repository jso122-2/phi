# -*- coding: utf-8 -*-
"""phi.ui._app._track_ui — apply track to UI surfaces + playback helpers.

CAIRRN scheduling
-----------------
Every track transition is routed through the ForestFloor (TRACK_TRANSITION →
CODE hub) before any UI surface is updated.

Operation priority tiers:
    IMMEDIATE  — transport controls, beat reset, waveform load (no gate)
    PREFEED    — ASCII art grid (PIL is expensive; computed off-thread)
    COHERENT   — sidebar, info drawer, lyrics load (coherent → now, else +250 ms)
    ALWAYS     — notification, mini player, Last.fm, media keys, vault query
                 (user-facing signals that must not be silently dropped)

DispatchResult.coherent is the gate signal:
    True  → CODE hub is settled → apply COHERENT ops immediately
    False → system is mid-transition → brief defer lets the floor stabilise
"""
from __future__ import annotations
import threading

from phi.engine.cairrn_router import RequestKind

# Delay (ms) applied to COHERENT-tier ops when the CODE hub is incoherent.
_INCOHERENT_DEFER_MS = 250


class _TrackUIMixin:
    """Update every UI surface when a new track starts; thin PlaybackController delegates."""

    def _apply_track_to_ui(self, path: str) -> None:
        """Update every UI surface after a new track has been loaded and started.

        Routes through CAIRRN (TRACK_TRANSITION) first.
        Art is prefed off-thread; sidebar/drawer/lyrics are gated by coherence.
        Transport-critical ops (duration, replaygain) run without gating.
        """
        # ── 1. CAIRRN route — CODE hub processes the transition ───────────────
        result = self.floor.router.route(
            RequestKind.TRACK_TRANSITION,
            metric=1.0,
            payload={"path": path},
        )
        coherent = result.coherent

        # ── 2. Metadata lookup ────────────────────────────────────────────────
        meta = self.library.get_meta(path)
        ann  = self.library.get_annotation(path) if hasattr(self.library, "get_annotation") else None

        # ── 3. IMMEDIATE — transport-critical (no CAIRRN gate) ───────────────
        if meta:
            if meta.get("duration"):
                self.duration = meta["duration"]
                self.transport.set_end(meta["duration"])
            self._apply_replaygain(meta)
        else:
            self.now_playing.set_title_only(path)
            threading.Thread(target=self._async_meta, args=(path,), daemon=True).start()

        # ── 4. ART — commit now if PIL already finished, else arm fallback ──────
        # PIL was started by _preload_art_for_path() in PlaybackController the
        # moment the path was known — before player.load(), before player.play().
        # By the time we reach here, PIL has had the full load+play window to
        # run.  commit_art_or_wait() is synchronous if the grid is ready (art
        # lands on the exact same Tk frame as the song switch), or installs a
        # callback that fires within ~5 ms of PIL finishing if it's still going.
        if meta:
            if meta.get("art_bytes"):
                self.now_playing.commit_art_or_wait(
                    on_ready=lambda: self._sched(0, self.now_playing.commit_art),
                )
            else:
                self.now_playing.set_track(path, meta)

        # ── 5. COHERENT — sidebar, info drawer, lyrics ────────────────────────
        # Always queued via _sched so they don't block the calling playback
        # controller; 0 ms when coherent, brief defer when in transition.
        defer_ms = 0 if coherent else _INCOHERENT_DEFER_MS

        def _update_coherent_surfaces():
            self.sidebar.update_info(path, meta, ann)
            self.info_drawer.update(path, meta, ann)
            self.tabs.lyrics_view.load(path, meta)

        self._sched(defer_ms, _update_coherent_surfaces)

        # ── 6. ALWAYS — hyphal, genre markers (lightweight, no gate) ─────────
        if hasattr(self.tabs, "hyphal_view"):
            self.tabs.hyphal_view.mark_playing(path)
        if hasattr(self.tabs, "genre_view"):
            self.tabs.genre_view.mark_playing(path)
        if hasattr(self, "_genre_page"):
            self._genre_page.mark_playing(path)

        # ── 7. ALWAYS — user-facing signals (notification, mini, scrobble) ───
        from phi.ui.settings_dialog import load_settings
        from phi.watch.notify import notify_track_change
        if meta and load_settings().get("notify_on_change", True):
            notify_track_change(
                title  = meta.get("title")  or "",
                artist = meta.get("artist") or "",
                album  = meta.get("album")  or "",
            )

        if hasattr(self, "_mini") and self._mini:
            self._mini.update_track(path, meta)
            self._mini.set_playing(True)

        if self._scrobbler and meta:
            import time as _time
            self._scrobble_ts = int(_time.time())
            self._scrobbler.now_playing(
                title    = meta.get("title")  or "",
                artist   = meta.get("artist") or "",
                album    = meta.get("album")  or "",
                duration = meta.get("duration") or 0.0,
            )

        # update_now_playing decodes album art into NSImage on macOS — off-thread
        # so it doesn't block the page change response.
        _mk = self.media_keys
        _m  = meta or {}
        threading.Thread(
            target=_mk.update_now_playing,
            kwargs={"meta": _m, "position": 0.0, "is_playing": True},
            daemon=True,
            name="phi-media-keys",
        ).start()
        self._vault_query_for_track(path, _m)

        # ── 8. CurveDaemon — A: fold inject, B: arc push, C: log play ────────
        if hasattr(self, "curve_daemon"):
            self.curve_daemon.on_track_change(path)

    def _preload_art_for_path(self, path: str) -> None:
        """Called by PlaybackController the moment a new path is known.

        Kicks off PIL in a background thread (via prefeed_art with no
        on_ready callback — commit_art_or_wait in _apply_track_to_ui will
        either commit synchronously if PIL finishes first, or arm the callback
        if PIL is still running).
        """
        meta = self.library.get_meta(path)
        if not meta:
            return
        art_bytes = meta.get("art_bytes")
        if not art_bytes:
            return
        cols = self.now_playing._cols
        rows = self.now_playing._rows
        self.now_playing.prefeed_art(art_bytes, cols, rows)

    # ── thin delegates to PlaybackController ─────────────────────────────────

    def _load_and_play(self, queue_pos: int) -> None:
        self.playback.load_and_play(queue_pos)

    def _advance(self) -> None:
        self.playback.advance()

    def _record_track_departure(self, prev_path: str) -> None:
        self.playback.record_departure(prev_path)

    def _play_path_direct(self, path: str) -> None:
        self.playback.play_path_direct(path)

    def _peek_next_path(self) -> str | None:
        return self.playback.peek_next_path()

    def _open_picker(self) -> None:
        """Ranker autopilot — always plays silently (NextPicker UI removed).

        Takes the first two ``candidates()`` paths (score → TP-RAR → Cc),
        applies a small ELO nudge, plays the gated winner.
        """
        cur_path = (
            self.library.playlist[self.queue.current_playlist_idx]
            if self.queue.current_playlist_idx >= 0
            and self.queue.current_playlist_idx < len(self.library.playlist)
            else None
        )

        top2 = self.ranker.candidates(self.library, cur_path, n=2)
        if not top2:
            nxt = self.queue.advance()
            if nxt is not None:
                self._load_and_play(nxt)
            else:
                self.player.stop()
                self.transport.set_playing(False)
            return

        # candidates() is already score → TP-RAR → Cc order; do not re-sort by score().
        winner = top2[0]
        loser  = top2[1] if len(top2) > 1 else winner
        self.ranker.elo_update(winner, loser, self.library, K=8)
        self._play_path_direct(winner)

    def on_toggle_ranker(self) -> None:
        """Toggle ranker on/off — can be bound to a settings button."""
        self.ranker_enabled = not self.ranker_enabled
        state = "on" if self.ranker_enabled else "off"
        self._flash(f"Smart next: {state}")

    def on_toggle_picker(self) -> None:
        """No-op — picker removed. Ranker always plays silently."""
