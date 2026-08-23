# -*- coding: utf-8 -*-
"""phi.core._poll_media_keys — rate-limited Now Playing / media-key sync tick."""
from __future__ import annotations

from typing import TYPE_CHECKING

from phi.core._poll_state import TickSnapshot

if TYPE_CHECKING:
    from phi.audio.media_keys import MediaKeyHandler


class MediaKeysTick:
    """Push Now Playing state to the system media-key handler.

    Runs every Nth poll tick to avoid hammering the platform API.

    Args:
        media_keys: System media-key / NowPlaying handler.
        every:      Fire every Nth poll tick (default 33 → every ~3.3 s at 100 ms).
    """

    def __init__(self, media_keys: "MediaKeyHandler", every: int = 33) -> None:
        self._media_keys = media_keys
        self._every = every
        self._counter: int = 0

    def tick(self, snap: TickSnapshot) -> None:
        """Advance the counter; push NowPlaying when due.

        Args:
            snap: Current tick snapshot — supplies ``pos``, ``busy``, ``playing``.
        """
        self._counter += 1
        if self._counter < self._every:
            return
        self._counter = 0

        if snap.duration > 0 and snap.raw_ms >= 0:
            self._media_keys.set_playback_state(snap.pos, snap.playing)
