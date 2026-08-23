# -*- coding: utf-8 -*-
"""phi.core.playback_controller — track-level playback state machine.

Owns the three operations that move the player from one track to another:
- ``load_and_play``  — load file into pygame and start playing.
- ``advance``        — end-of-track logic (repeat, ranker, queue advance).
- ``record_departure`` — stats / ELO / scrobble for the track being left.

UI side-effects (NowPlaying update, picker widget) are inverted as callbacks so
this class stays import-free from any UI framework.
"""
from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING, Callable, Optional

import phi.session as _phi_session
from phi.core.history import PlaybackHistory

if TYPE_CHECKING:
    from phi.core.library import Library
    from phi.core.player import PlayerEngine
    from phi.core.queue import QueueEngine
    from phi.core.race_watcher import PhiRaceWatcher
    from phi.core.ranker import TrackRanker
    from phi.core.meta_worker import MetaWorker
    from phi.audio.beat import BeatSimulator
    from phi.engine.forest_floor import ForestFloor


class PlaybackController:
    """Stateful playback controller: owns duration and track-start cursor.

    Args:
        player:               Audio playback engine.
        queue:                Playback queue.
        library:              Track library.
        transport:            Transport bar widget.
        race_watcher:         Race-condition guard.
        ranker:               Track ranking engine.
        beat:                 Beat simulator (reset on track load).
        floor:                ForestFloor for CAIRRN events.
        schedule:             ``widget.after`` — post to main thread.
        flash:                ``(msg, ms=3000) -> None`` — display flash message.
        meta_worker:          MetaWorker for async meta / duration fetch.
        on_apply_track_to_ui: ``(path) -> None`` — update NowPlaying/sidebar/etc.
        on_open_picker:       ``() -> None`` — show NextPicker overlay.
        on_play_path:         ``(path) -> None`` — add path to queue and play.
        on_refresh_playlist:  ``() -> None`` — sync PlaylistPanel with queue state.
        get_ranker_enabled:   ``() -> bool``
        get_picker_enabled:   ``() -> bool``
        get_duration:         ``() -> float`` — read the shared duration.
        set_duration:         ``(float) -> None`` — write the shared duration.
        scrobbler:            Optional Last.fm scrobbler.
    """

    def __init__(
        self,
        player: "PlayerEngine",
        queue: "QueueEngine",
        library: "Library",
        transport,
        race_watcher: "PhiRaceWatcher",
        ranker: "TrackRanker",
        beat: "BeatSimulator",
        floor: "ForestFloor",
        schedule: Callable,
        flash: Callable[[str], None],
        meta_worker: "MetaWorker",
        on_apply_track_to_ui: Callable[[str], None],
        on_open_picker: Callable[[], None],
        on_play_path: Callable[[str], None],
        on_refresh_playlist: Callable[[], None],
        get_ranker_enabled: Callable[[], bool],
        get_picker_enabled: Callable[[], bool],
        get_duration: Callable[[], float],
        set_duration: Callable[[float], None],
        scrobbler=None,
        on_preload_art: "Callable[[str], None] | None" = None,
        on_skip: "Callable[[str, float], None] | None" = None,
    ) -> None:
        self._player = player
        self._queue = queue
        self._library = library
        self._transport = transport
        self._race_watcher = race_watcher
        self._ranker = ranker
        self._beat = beat
        self._floor = floor
        self._schedule = schedule
        self._flash = flash
        self._meta_worker = meta_worker
        self._on_apply_track_to_ui = on_apply_track_to_ui
        self._on_open_picker = on_open_picker
        self._on_play_path = on_play_path
        self._on_refresh_playlist = on_refresh_playlist
        self._get_ranker_enabled = get_ranker_enabled
        self._get_picker_enabled = get_picker_enabled
        self._get_duration = get_duration
        self._set_duration = set_duration
        self._scrobbler = scrobbler
        self._on_preload_art = on_preload_art
        self._on_skip = on_skip
        self._scrobble_ts: float | None = None

        self._track_start_pos: float = 0.0
        self.history = PlaybackHistory()

    # ──────────────────────────────────────── load / advance ──

    def load_and_play(self, queue_pos: int) -> None:
        """Load the track at *queue_pos* and start playback.

        Raises: nothing — errors are reported via flash and auto-skipped.
        """
        if not (0 <= queue_pos < len(self._queue.queue)):
            return

        self._race_watcher.on_load_and_play(self._player)

        prev_playlist_idx = self._queue.current_playlist_idx
        if 0 <= prev_playlist_idx < len(self._library.playlist):
            self.record_departure(self._library.playlist[prev_playlist_idx])

        self._queue.pos = queue_pos
        playlist_idx = self._queue.queue[queue_pos]
        path = self._library.playlist[playlist_idx]

        if not os.path.isfile(path):
            self._flash(f"⚠ Not found: {os.path.basename(path)}")
            self._schedule(400, self.advance)
            return

        # Fire art prefeed the moment we know the path — PIL runs in parallel
        # with player.load() + play() so the grid is ready (or close to it) by
        # the time _on_apply_track_to_ui is called.
        if self._on_preload_art is not None:
            self._on_preload_art(path)

        try:
            self._player.load(path)
            self._player.play()
        except Exception as exc:
            self._flash(f"⚠ Can't play: {os.path.basename(path)}  ({exc})")
            self._schedule(400, self.advance)
            return

        self._track_start_pos = 0.0
        self._set_duration(0.0)
        self._beat.reset(path)
        self._library.record_play(path)
        self._transport.set_playing(True)
        self._transport.reset_seek()
        self._transport.set_end("…")
        self._transport.load_waveform(path)

        # Record in the doubly-linked playback history
        self.history.push(path, queue_pos, playlist_idx)

        # Feed history depth into the CAIRRN substrate so the IPC state
        # and MCP tools always reflect the real listening chain.
        recent = [n.path for n in self.history.recent(5)]
        self._floor.track_history_feed(
            depth_back    = self.history.depth_back(),
            depth_forward = self.history.depth_forward(),
            recent_paths  = recent,
        )

        # Defer the UI fan-out (NowPlaying, art, sidebar) to the next event-loop
        # tick so the current load_and_play frame returns immediately.  AVPlayer's
        # _play_when_ready thread can fire player.play() before the event loop is
        # blocked by image loading and SQL reads.
        self._schedule(0, lambda p=path: self._on_apply_track_to_ui(p))

        self._meta_worker.fetch_duration(path)
        self._schedule(0, self._on_refresh_playlist)

    def advance(self) -> None:
        """End-of-track logic: respect repeat modes, open picker, or advance queue.

        Called at end of track or after a crossfade completes.
        """
        if self._race_watcher.on_advance(self._queue.pos, self._player):
            return

        if self._queue.repeat in ("one", "all"):
            # Skip rebuild in CAIRRN mode — the arc engine drives selection by
            # inserting its suggestion at pos+1 via on_play_next_path().
            # Rebuilding would destroy that pre-queued slot and revert to
            # sequential / random order on every advance.
            if self._queue.repeat == "all" and self._queue.shuffle and self._queue.shuffle_mode != "cairrn":
                self._queue.rebuild(self._library.size, keep_current=False)
                self._schedule(0, self._on_refresh_playlist)
            nxt = self._queue.advance()
            if nxt is not None:
                self.load_and_play(nxt)
            else:
                self._player.stop()
                self._transport.set_playing(False)
            return

        if self._get_ranker_enabled() and self._library.size >= 3:
            self._on_open_picker()
        else:
            nxt = self._queue.advance()
            if nxt is not None:
                self.load_and_play(nxt)
            else:
                self._player.stop()
                self._transport.set_playing(False)

    def record_departure(self, prev_path: str) -> None:
        """Record stats, ELO, and scrobble for the track being left.

        Must never raise — any failure here is non-fatal telemetry.
        Exceptions from CAIRRN routing (e.g. bridge OverflowError from a
        runaway GNN metric) are caught so load_and_play() always proceeds.
        """
        try:
            self._record_departure_inner(prev_path)
        except Exception:
            import logging, traceback
            logging.getLogger("phi.playback").warning(
                "record_departure non-fatal: %s", traceback.format_exc()
            )

    def _record_departure_inner(self, prev_path: str) -> None:
        """Inner implementation of record_departure — may raise."""
        elapsed = max(0.0, self._player.position() - self._track_start_pos)
        self._library.record_play_progress(prev_path, elapsed)

        prev_dur = float((self._library.get_meta(prev_path) or {}).get("duration") or 0)
        completion_rate = (elapsed / prev_dur) if prev_dur > 0 else 0.5
        if prev_dur > 0 and completion_rate < 0.30:
            self._library.record_skip(prev_path)
            if self._on_skip is not None:
                self._on_skip(prev_path, elapsed)

        self._ranker.implicit_elo_update(prev_path, self._library)

        # Persist ELO in a lightweight sidecar so rankings survive unclean shutdowns.
        # Fire-and-forget: write is cheap (~few KB) and non-blocking.
        _snap = dict(self._library.play_stats)
        threading.Thread(
            target=_phi_session.save_play_stats,
            args=(_snap,),
            daemon=True,
            name="phi-elo-save",
        ).start()

        _prev_meta = self._library.get_meta(prev_path) or {}
        _prev_ann = self._library.get_annotation(prev_path) or {}
        self._floor.leaf_falls(
            prev_path,
            completion_rate,
            album=_prev_meta.get("album") or "",
            genre=(_prev_meta.get("genre") or _prev_ann.get("genre") or ""),
            mood=(_prev_ann.get("spotify_mood") or _prev_ann.get("mood") or ""),
        )

        if prev_dur > 0 and completion_rate < 0.30:
            skip_pressure = max(0.0, 1.0 - completion_rate)
            self._floor.skip_event(prev_path, skip_pressure)

        if self._scrobbler and self._scrobble_ts:
            prev_meta = self._library.get_meta(prev_path) or {}
            if self._scrobbler.should_scrobble(elapsed, prev_dur):
                self._scrobbler.scrobble(
                    title=prev_meta.get("title") or "",
                    artist=prev_meta.get("artist") or "",
                    album=prev_meta.get("album") or "",
                    duration=prev_dur,
                    timestamp=self._scrobble_ts,
                )

    def play_path_direct(self, path: str) -> None:
        """Navigate to *path* in the queue (or add it) and begin playback."""
        playlist_idx = self._library.playlist_index(path)
        if playlist_idx is not None:
            for queue_pos, pl_idx in enumerate(self._queue.queue):
                if pl_idx == playlist_idx:
                    self.load_and_play(queue_pos)
                    return
        self._on_play_path(path)

    def peek_next_path(self) -> str | None:
        """Return the absolute path of the next track in queue, or None."""
        next_pos = self._queue.pos + 1
        if next_pos >= len(self._queue.queue):
            if self._queue.repeat == "all":
                next_pos = 0
            else:
                return None
        pl_idx = self._queue.queue[next_pos]
        if pl_idx >= len(self._library.playlist):
            return None
        return self._library.playlist[pl_idx]

    def handoff_after_crossfade(self, path: str) -> None:
        """Queue/UI sync when crossfade already started playback of *path*."""
        playlist_idx = self._library.playlist_index(path)
        if playlist_idx is None:
            self.advance()
            return

        queue_pos: int | None = None
        nxt = self._queue.next_user()
        if nxt is not None and self._queue.queue[nxt] == playlist_idx:
            queue_pos = nxt
        else:
            try:
                queue_pos = self._queue.queue.index(playlist_idx)
            except ValueError:
                self.advance()
                return

        prev_playlist_idx = self._queue.current_playlist_idx
        if 0 <= prev_playlist_idx < len(self._library.playlist):
            self.record_departure(self._library.playlist[prev_playlist_idx])

        self._queue.pos = queue_pos
        self._track_start_pos = 0.0
        self._set_duration(0.0)
        self._beat.reset(path)
        self._library.record_play(path)
        self._transport.set_playing(True)
        self._transport.reset_seek()
        self._transport.set_end("…")
        self._transport.load_waveform(path)
        self.history.push(path, queue_pos, playlist_idx)
        recent = [n.path for n in self.history.recent(5)]
        self._floor.track_history_feed(
            depth_back=self.history.depth_back(),
            depth_forward=self.history.depth_forward(),
            recent_paths=recent,
        )
        self._schedule(0, lambda p=path: self._on_apply_track_to_ui(p))
        self._meta_worker.fetch_duration(path)
        self._schedule(0, self._on_refresh_playlist)
