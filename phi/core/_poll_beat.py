# -*- coding: utf-8 -*-
"""phi.core._poll_beat — beat simulation and visualiser energy tick."""
from __future__ import annotations

from typing import TYPE_CHECKING

from phi.core._poll_state import TickSnapshot

if TYPE_CHECKING:
    from phi.audio.beat import BeatSimulator


class BeatTick:
    """Drive the beat simulator and push energy to the visualiser widgets.

    Writes ``snap.energy`` and ``snap.on_beat`` so downstream handlers can
    read energy without knowing about the beat simulator.

    Args:
        beat:   Beat simulator (``set_state`` + ``tick``).
        hyphal: Hyphal panel widget (``set_energy``).
        wave:   Optional wave widget (``set_energy``).
    """

    def __init__(self, beat: "BeatSimulator", hyphal, wave=None) -> None:
        self._beat = beat
        self._hyphal = hyphal
        self._wave = wave

    def tick(self, snap: TickSnapshot, poll_ms: float) -> None:
        """Update beat state, compute energy, push to visualisers.

        Mutates ``snap.energy`` and ``snap.on_beat`` in-place.

        Args:
            snap:    Current tick snapshot; energy/on_beat written here.
            poll_ms: Poll interval in ms — passed directly to ``beat.tick()``.
        """
        self._beat.set_state(snap.playing, snap.paused)
        energy, on_beat = self._beat.tick(poll_ms)
        snap.energy = energy
        snap.on_beat = on_beat

        self._hyphal.set_energy(energy, on_beat, snap.playing)
        if self._wave is not None:
            self._wave.set_energy(energy, snap.playing)
