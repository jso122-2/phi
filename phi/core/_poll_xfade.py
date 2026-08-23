# -*- coding: utf-8 -*-
"""phi.core._poll_xfade — crossfade state machine and gapless preload tick.

Crossfade and gapless are mutually exclusive (gapless only runs when
``CROSSFADE_SECS == 0``), so they live in the same handler.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from phi.config import CROSSFADE_SECS, GAPLESS, POLL_MS
from phi.core._poll_state import TickSnapshot

if TYPE_CHECKING:
    from phi.core.player import PlayerEngine
    from phi.core.queue import QueueEngine
    from phi.core.race_watcher import PhiRaceWatcher


class XfadeGaplessTick:
    """Crossfade state machine + gapless pre-queue.

    Owns ``_xfade_advanced`` and ``_gapless_queued`` so the orchestrator
    does not need to track them.  Call ``reset_gapless()`` after an
    end-of-track advance so the flag clears for the next track.

    Args:
        player:               Audio playback engine.
        queue:                Playback queue (gapless guard only).
        race_watcher:         Race-condition guard.
        peek_next_path:       Returns the next queued track path (or None).
        on_advance:           Fired at end of crossfade when handoff is missing.
        on_crossfade_handoff: Optional — called with the promoted path.
    """

    def __init__(
        self,
        player: "PlayerEngine",
        queue: "QueueEngine",
        race_watcher: "PhiRaceWatcher",
        peek_next_path: Callable[[], Optional[str]],
        on_advance: Callable[[], None],
        on_crossfade_handoff: Callable[[str], None] | None = None,
    ) -> None:
        self._player = player
        self._queue = queue
        self._race_watcher = race_watcher
        self._peek_next_path = peek_next_path
        self._on_advance = on_advance
        self._on_crossfade_handoff = on_crossfade_handoff

        self._xfade_advanced: bool = False
        self._gapless_queued: bool = False

    @property
    def xfade_handled(self) -> bool:
        """True if a crossfade completion was handled this tick."""
        return self._xfade_advanced

    def reset_gapless(self) -> None:
        """Clear the gapless-queued flag after an end-of-track advance."""
        self._gapless_queued = False

    def tick(self, snap: TickSnapshot) -> None:
        """Advance crossfade or trigger gapless pre-queue.

        Sets ``_xfade_advanced`` as a side-effect; read via ``xfade_handled``
        before the end-of-track check in the orchestrator.

        Args:
            snap: Current tick snapshot.
        """
        self._xfade_advanced = False
        self._tick_crossfade(snap)
        self._tick_gapless(snap)

    # ── internal ──────────────────────────────────────────────────────────

    def _tick_crossfade(self, snap: TickSnapshot) -> None:
        if self._player._xfading:
            still_fading = self._player.tick_crossfade(POLL_MS / 1000.0)
            if not still_fading:
                path = self._player.finish_crossfade_promote()
                self._xfade_advanced = True
                if path and self._on_crossfade_handoff:
                    self._on_crossfade_handoff(path)
                else:
                    self._on_advance()
            return

        if CROSSFADE_SECS <= 0 or snap.duration <= 0 or not snap.playing or snap.raw_ms < 0:
            return

        time_left = snap.duration - snap.pos
        if 0 < time_left <= CROSSFADE_SECS:
            next_path = self._peek_next_path()
            if next_path:
                self._player.begin_crossfade(next_path, CROSSFADE_SECS)

    def _tick_gapless(self, snap: TickSnapshot) -> None:
        if CROSSFADE_SECS != 0 or not GAPLESS:
            return
        if not snap.playing or snap.duration <= 0 or snap.raw_ms < 0:
            return
        if self._race_watcher.on_gapless_queue(self._gapless_queued):
            return
        if snap.duration - snap.pos <= 5.0:
            from phi.core.queue import should_prefetch
            if not should_prefetch():
                return
            next_path = self._peek_next_path()
            if next_path and self._player.queue_next(next_path):
                self._gapless_queued = True
