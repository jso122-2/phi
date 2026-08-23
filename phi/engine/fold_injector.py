# -*- coding: utf-8 -*-
"""phi.engine.fold_injector — inject track fold-bits into the shared harmonic index.

Each fold bit encodes a right (1) or left (0) turn on the dragon curve and maps
directly onto one of the 8 harmonic shards:

    bit=1  →  inject  +ALPHA * weight  (right attractor side)
    bit=0  →  inject  −ALPHA * weight  (left attractor side)

The injection is additive (not a reset), and one local-diffusion propagation
step follows each call so κ=0.15 coupling has a chance to smooth the ring
before the next track arrives.
"""
from __future__ import annotations

from typing import Sequence

from sims.harmonic import HarmonicIndex
from sims.attractors import ALPHA


class FoldInjector:
    """Wire an 8-bit fold sequence from track metadata into the harmonic index.

    Args:
        index:  Shared ``HarmonicIndex`` — the same instance bound to the
                CAIRRN dispatcher in ``app.py`` (``self._cairrn_index``).
        weight: Fraction of ALPHA injected per shard per track.
                1.0 = full attractor jump; 0.4 = gentle nudge (default).
    """

    def __init__(self, index: HarmonicIndex, weight: float = 0.4) -> None:
        if not 0.0 < weight <= 1.0:
            raise ValueError(f"weight must be in (0, 1]; got {weight}")
        self._index = index
        self._weight = float(weight)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def inject(self, fold_bits: Sequence[int] | None) -> None:
        """Inject fold_bits into the harmonic index and propagate one step.

        Args:
            fold_bits: Sequence of up to 8 ints (0 or 1). If ``None`` or
                       shorter than 8, the missing positions default to 0
                       (left-attractor, neutral nudge).
        """
        if not fold_bits:
            return

        bits = list(fold_bits)[:8]
        bits += [0] * (8 - len(bits))  # pad if < 8 bits supplied

        for shard_idx, bit in enumerate(bits):
            # Maps: bit=0 → −ALPHA*w (left), bit=1 → +ALPHA*w (right)
            value = (2 * int(bool(bit)) - 1) * ALPHA * self._weight
            self._index.inject(shard_idx, value)

        # One diffusion step lets κ=0.15 coupling smooth the newly-set state
        self._index.propagate(steps=1, mode="local")

    def state(self) -> dict:
        """Serialisable snapshot of the current harmonic index state."""
        return self._index.state()

    def __repr__(self) -> str:
        return f"FoldInjector(weight={self._weight}, shards={len(self._index.shards)})"
