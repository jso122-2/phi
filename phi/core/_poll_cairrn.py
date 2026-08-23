# -*- coding: utf-8 -*-
"""phi.core._poll_cairrn — CAIRRN heartbeat + dispatcher step, off the main thread.

Both ``floor.heartbeat()`` and ``dispatcher.step()`` can be slow (neural inference,
CAIRRN routing, mycelial tick).  Neither must run on the Qt main thread.
A single daemon thread handles them sequentially so heartbeat always precedes step.
The ``_running`` flag prevents a backlog when a tick takes longer than the cadence.
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Optional

from phi.core._poll_state import TickSnapshot

if TYPE_CHECKING:
    from phi.engine.forest_floor import ForestFloor


class CairnTick:
    """Rate-limited off-thread CAIRRN heartbeat + dispatcher step.

    Args:
        floor:      ForestFloor — ``heartbeat(progress, energy)`` called each tick.
        dispatcher: Optional CAIRRNDispatcher — ``step()`` called after heartbeat.
        every:      Fire every Nth poll tick (default 10 → every 1 s at 100 ms poll).
    """

    def __init__(
        self,
        floor: "ForestFloor",
        dispatcher=None,
        every: int = 10,
    ) -> None:
        self._floor = floor
        self._dispatcher = dispatcher
        self._every = every
        self._counter: int = 0
        self._running: bool = False

    def tick(self, snap: TickSnapshot) -> None:
        """Advance the counter; fire the off-thread CAIRRN tick when due.

        No-ops if a previous tick is still running (prevents backlog).

        ``dispatcher.step()`` runs every eligible tick regardless of playback
        state so the coherence gate keeps building between tracks.
        ``floor.heartbeat()`` is gated by active playback (needs a valid
        progress/duration signal).

        Args:
            snap: Current tick snapshot — supplies ``pos``, ``duration``, ``energy``.
        """
        self._counter += 1
        if self._counter < self._every:
            return
        self._counter = 0

        if self._running:
            return

        has_playback = snap.duration > 0 and snap.raw_ms >= 0

        self._running = True
        progress = min(1.0, snap.pos / snap.duration) if has_playback else 0.0
        energy   = snap.energy if has_playback else 0.0
        floor      = self._floor
        dispatcher = self._dispatcher

        def _do() -> None:
            try:
                if has_playback:
                    floor.heartbeat(progress=progress, energy=energy)
                if dispatcher is not None:
                    dispatcher.step()
            except Exception:
                pass
            finally:
                self._running = False

        threading.Thread(target=_do, daemon=True, name="cairrn-tick").start()
