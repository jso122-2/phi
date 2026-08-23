# -*- coding: utf-8 -*-
"""phi.core.race_watcher — Pericles-pattern playback race condition watchdog.

Mirrors the PericlesWatchdog in spawn_tracer.py, adapted for phi's
real-time poll loop rather than batch cycles.

Five race conditions monitored
──────────────────────────────
    DOUBLE_PLAY       channel-0 busy while _xfading is False
                      → channel-0 was not stopped after a crossfade completed
                      → escalation: abort_crossfade() to silence rogue channel

    XFADE_HANG        _xfading True for longer than 2× CROSSFADE_SECS
                      → crossfade tick loop hung or never completed
                      → escalation: abort_crossfade(), let normal advance proceed

    SKIP_DURING_XFADE _load_and_play() called while _xfading is True
                      → music channel replaced mid-fade; channel-0 would keep playing
                      → escalation: abort_crossfade() before the load

    DOUBLE_ADVANCE    _advance() called for the same queue position twice
                      → end-of-track detection fired more than once per track
                      → escalation: suppress second call (log only)

    GAPLESS_DRIFT     queue_next() about to fire while _gapless_queued is True
                      → gapless flag lost between ticks
                      → escalation: suppress re-queue (log only)

Usage
─────
    # in PhiApp.__init__:
    from phi.engine.race_watcher import PhiRaceWatcher
    self.race_watcher = PhiRaceWatcher(player=self.player)

    # in _poll():
    self.race_watcher.poll_tick(self.player, self.queue)

    # in _advance():
    if self.race_watcher.on_advance(self.queue.pos, self.player):
        return   # suppressed — already handled

    # in _load_and_play() before player.load():
    self.race_watcher.on_load_and_play(self.player)

    # in _poll_gapless() before queue_next():
    if self.race_watcher.on_gapless_queue(self):
        return   # suppressed — already queued
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from phi.core.player import PlayerEngine
    from phi.core.queue  import QueueEngine

logger = logging.getLogger("phi.race_watcher")


class PhiRaceWatcher:
    """
    Pericles-pattern watchdog for phi playback race conditions.

    Tracks five health signals across the poll loop and key event hooks.
    Escalates through: warn → auto-recover → (log-only for non-recoverable).

    Args:
        max_double_play_streak:  consecutive ticks of channel-0 leak before abort
        max_xfade_hang_ticks:    consecutive ticks of stuck xfade before abort
                                 (0 = auto from CROSSFADE_SECS)
        poll_ms:                 poll interval in ms (used for hang calculation)
        crossfade_secs:          expected fade duration (used for hang threshold)
    """

    def __init__(
        self,
        max_double_play_streak: int  = 2,
        max_xfade_hang_ticks:   int  = 0,
        poll_ms:                float = 150.0,
        crossfade_secs:         float = 3.0,
    ) -> None:
        self._poll_ms          = poll_ms
        self._crossfade_secs   = crossfade_secs

        # Hang threshold: 2.5× the expected fade duration in ticks
        self._hang_ticks_max   = max_xfade_hang_ticks or int(
            crossfade_secs * 2.5 * 1000 / poll_ms
        )
        self._dp_streak_max    = max_double_play_streak

        # ── streaks ───────────────────────────────────────────────────────────
        self._double_play_streak:  int = 0
        self._xfade_hang_ticks:    int = 0
        self._xfade_start_ts:    float = 0.0

        # ── totals (lifetime) ─────────────────────────────────────────────────
        self._total_double_play:   int = 0
        self._total_xfade_hang:    int = 0
        self._total_skip_mid_xfade:int = 0
        self._total_double_advance:int = 0
        self._total_gapless_drift: int = 0

        # ── advance dedup ─────────────────────────────────────────────────────
        self._last_advance_pos:    int   = -999   # queue_pos of last _advance call
        self._last_advance_ts:     float = 0.0    # wall-clock time

        self._total_ticks: int = 0

        # ── Pericles watchdog (optional) ──────────────────────────────────────
        # Attached after construction via attach_dr_watchdog().
        # When wired, DOUBLE_ADVANCE events are scored and forwarded so they
        # appear alongside dispatcher DOUBLE_ROUTE events in watchdog state().
        self._dr_watchdog: Optional[Any] = None

    # =========================================================================
    # Watchdog wiring
    # =========================================================================

    def attach_dr_watchdog(self, watchdog: Any) -> None:
        """
        Wire a DoubleRouteWatchdog for Pericles-scored song-transition tracking.

        When attached, every DOUBLE_ADVANCE event is forwarded to
        ``watchdog.observe_song_transition()`` so race conditions during song
        transitions appear alongside dispatcher DOUBLE_ROUTE events in the
        unified watchdog state.

        Call once from PhiApp / make_phi_pipeline() after both the dispatcher
        watchdog and the race watcher are constructed:

            watcher.attach_dr_watchdog(dispatcher._dr_watchdog)
        """
        self._dr_watchdog = watchdog

    # =========================================================================
    # Poll-tick — called every POLL_MS from _poll()
    # =========================================================================

    def poll_tick(self, player: "PlayerEngine", queue: "QueueEngine") -> None:
        """
        Passive scan: detects DOUBLE_PLAY and XFADE_HANG on every poll tick.
        Call at the start of _poll() before any action is taken.
        """
        self._total_ticks += 1

        # ── DOUBLE_PLAY ───────────────────────────────────────────────────────
        # channel-0 (xfade channel) busy but the _xfading flag is already clear
        # → crossfade completed/aborted but channel-0 was never stopped.
        if player.xfade_channel_busy and not player._xfading:
            self._double_play_streak += 1
            self._total_double_play  += 1
            logger.warning(
                "PhiRaceWatcher [DOUBLE_PLAY] xfade channel leaked "
                "(streak=%d / max=%d)  total=%d",
                self._double_play_streak, self._dp_streak_max,
                self._total_double_play,
            )
            if self._double_play_streak >= self._dp_streak_max:
                logger.warning(
                    "PhiRaceWatcher [DOUBLE_PLAY] streak threshold reached "
                    "— aborting rogue xfade channel"
                )
                player.abort_crossfade()
                self._double_play_streak = 0
        else:
            self._double_play_streak = 0

        # ── XFADE_HANG ────────────────────────────────────────────────────────
        # _xfading has been True for longer than 2.5× CROSSFADE_SECS.
        if player._xfading:
            if self._xfade_start_ts == 0.0:
                self._xfade_start_ts = time.monotonic()
            self._xfade_hang_ticks += 1
            if self._xfade_hang_ticks >= self._hang_ticks_max:
                elapsed = time.monotonic() - self._xfade_start_ts
                logger.warning(
                    "PhiRaceWatcher [XFADE_HANG] crossfade stuck for "
                    "%.1fs (%d ticks, max=%d) — aborting",
                    elapsed, self._xfade_hang_ticks, self._hang_ticks_max,
                )
                player.abort_crossfade()
                self._total_xfade_hang  += 1
                self._xfade_hang_ticks   = 0
                self._xfade_start_ts     = 0.0
        else:
            self._xfade_hang_ticks = 0
            self._xfade_start_ts   = 0.0

    # =========================================================================
    # Event hooks — called at key decision points
    # =========================================================================

    def on_load_and_play(self, player: "PlayerEngine") -> None:
        """
        SKIP_DURING_XFADE: call at the top of _load_and_play(), before
        player.load().  Aborts any active crossfade so channel-0 is silenced
        before the music channel is replaced.
        """
        if player._xfading:
            self._total_skip_mid_xfade += 1
            logger.info(
                "PhiRaceWatcher [SKIP_DURING_XFADE] load_and_play fired "
                "mid-crossfade — aborting xfade channel  total=%d",
                self._total_skip_mid_xfade,
            )
            player.abort_crossfade()

    def on_advance(self, queue_pos: int, player: "PlayerEngine") -> bool:
        """
        DOUBLE_ADVANCE: call at the top of _advance().

        Returns True if this advance should be suppressed (duplicate call for
        the same queue position within a very short window).  Caller should
        return immediately if True.
        """
        now = time.monotonic()
        same_pos  = (queue_pos == self._last_advance_pos)
        rapid     = (now - self._last_advance_ts) < (self._poll_ms * 3 / 1000.0)

        if same_pos and rapid and queue_pos >= 0:
            self._total_double_advance += 1
            dt_ms = (now - self._last_advance_ts) * 1000.0
            logger.warning(
                "PhiRaceWatcher [DOUBLE_ADVANCE] _advance() called twice "
                "for queue_pos=%d within %.0fms (dt=%.1fms)  total=%d",
                queue_pos, self._poll_ms * 3, dt_ms, self._total_double_advance,
            )
            # Forward to the Pericles watchdog for Euler-scored event tracking
            if self._dr_watchdog is not None:
                try:
                    self._dr_watchdog.observe_song_transition(
                        queue_pos=queue_pos,
                        dt_ms=dt_ms,
                    )
                except Exception:
                    pass
            return True   # suppress

        self._last_advance_pos = queue_pos
        self._last_advance_ts  = now
        return False

    def on_gapless_queue(self, gapless_queued: bool) -> bool:
        """
        GAPLESS_DRIFT: call before queue_next() in _poll_gapless().

        Returns True if the queue attempt should be suppressed because
        _gapless_queued is already set (flag drift).  Caller should
        return immediately if True.
        """
        if gapless_queued:
            self._total_gapless_drift += 1
            logger.debug(
                "PhiRaceWatcher [GAPLESS_DRIFT] queue_next fired while "
                "_gapless_queued=True  total=%d",
                self._total_gapless_drift,
            )
            return True
        return False

    # =========================================================================
    # Status
    # =========================================================================

    def status_line(self) -> str:
        """One-line health summary, mirrors PericlesWatchdog.status_line()."""
        return (
            f"PhiRace  ticks={self._total_ticks}"
            f"  double_play={self._total_double_play}"
            f"  xfade_hang={self._total_xfade_hang}"
            f"  skip_mid_xfade={self._total_skip_mid_xfade}"
            f"  double_advance={self._total_double_advance}"
            f"  gapless_drift={self._total_gapless_drift}"
        )
