# -*- coding: utf-8 -*-
"""phi.audio.beat — tempo-seeded beat simulator.

Produces convincing kick+snare+hihat energy and on-beat pulses without
requiring real audio analysis. BPM is seeded from the track's filename hash
so the same song always gets the same tempo feel.
"""
from __future__ import annotations
import math
import random


class BeatSimulator:
    """
    Simulates a drum-machine-like energy envelope at a track-specific BPM.

    Layers
    ------
    kick   — sharp attack every beat, exponential decay (most energy)
    snare  — beats 2 and 4 in a 4/4 bar
    hihat  — eighth-note subdivisions (subtle shimmer)
    drift  — slow ambient swell that follows a longer phrase structure

    Usage
    -----
    sim = BeatSimulator()
    sim.reset(path)          # call on every new track
    energy, on_beat = sim.tick(dt_ms)   # call each poll frame
    """

    def __init__(self) -> None:
        self._bpm      = 120.0
        self._t        = 0.0       # time in seconds
        self._prev_phi = 0.0       # last beat phase (for edge detection)
        self._noise    = 0.0       # slow noise state
        self._playing  = False
        self._paused   = False

    # ── public API ────────────────────────────────────────────────────────────

    def reset(self, path: str = "") -> None:
        """
        Seed BPM and phase from *path* so the same song always feels the same.
        BPM is drawn uniformly from [88, 132].
        """
        seed = sum(ord(c) for c in path) if path else 42
        rng  = random.Random(seed)
        self._bpm   = rng.uniform(88.0, 132.0)
        self._t     = rng.uniform(0.0, 60.0 / self._bpm)   # random phrase offset
        self._noise = 0.0

    def set_state(self, playing: bool, paused: bool) -> None:
        self._playing = playing
        self._paused  = paused

    def tick(self, dt_ms: float) -> tuple[float, bool]:
        """
        Advance the simulator by *dt_ms* milliseconds.

        Returns
        -------
        energy : float   [0, 1]  — current energy level
        on_beat : bool           — True on the first frame of each kick hit
        """
        if not self._playing:
            # Stopped: near-zero; paused: very slow ambient glow
            if self._paused:
                return 0.08 + 0.04 * math.sin(self._t * 0.3), False
            return 0.0, False

        self._t += dt_ms / 1000.0

        beats_per_sec = self._bpm / 60.0
        phi     = (self._t * beats_per_sec) % 1.0   # 0→1 each beat
        bar_phi = (self._t * beats_per_sec / 4) % 1.0  # 0→1 each bar

        # ── kick: sharp attack at every beat ─────────────────────────────────
        kick   = math.exp(-phi * 6.0) * 0.85

        # ── snare: beats 2 and 4 (half-time at bar_phi = 0.25, 0.75) ────────
        snare_phi  = (self._t * beats_per_sec / 2) % 1.0
        snare      = math.exp(-snare_phi * 7.0) * 0.45

        # ── hi-hat: 8th notes ─────────────────────────────────────────────────
        hat_phi  = (self._t * beats_per_sec * 2) % 1.0
        hihat    = max(0.0, 1.0 - hat_phi * 6.0) * 0.15

        # ── phrase swell: gentle 8-bar energy arc ────────────────────────────
        swell = 0.5 + 0.5 * math.sin(bar_phi * math.pi)
        swell *= 0.2

        # ── slow noise ────────────────────────────────────────────────────────
        self._noise += (random.random() - 0.5) * 0.04
        self._noise *= 0.92
        self._noise  = max(-0.08, min(0.08, self._noise))

        energy = kick + snare + hihat + swell + self._noise
        energy = max(0.0, min(1.0, energy))

        # Beat edge: phi just crossed 0 (wrapped around)
        on_beat    = phi < self._prev_phi        # wrapped
        self._prev_phi = phi

        return energy, on_beat

    @property
    def bpm(self) -> float:
        return self._bpm
