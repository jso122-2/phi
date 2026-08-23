# -*- coding: utf-8 -*-
"""phi.core._poll_state — per-tick player snapshot shared by all sub-tick handlers."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TickSnapshot:
    """Immutable-by-convention snapshot of player state for one poll tick.

    Captured once per tick from a single ``player.tick_state()`` call so every
    sub-handler operates on the same consistent view without extra ObjC round-trips.

    ``energy`` and ``on_beat`` are written by :class:`BeatTick` before any other
    handler reads them.
    """

    busy: bool
    raw_ms: int
    pos: float
    duration: float
    paused: bool
    playing: bool       # = busy and not paused

    energy: float = field(default=0.0)
    on_beat: bool = field(default=False)
