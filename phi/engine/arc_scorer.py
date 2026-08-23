# -*- coding: utf-8 -*-
"""phi.engine.arc_scorer — rolling D4_A buffer for smooth arc-transition scoring.

Maintains a circular buffer of recent D4_A values from playback history and
exposes ``score_candidate(d4_a)`` to rate how well a candidate track continues
the current arc.

Scoring model
-------------
    level  = mean(buffer)          — where the arc currently sits
    slope  = linregress(last 8)    — building vs. releasing energy?
    target = level + slope         — next expected value on the arc

    score(d4_a) = 1 / (1 + |d4_a − target| * scale)
                = 1.0  → perfect continuation (delta = 0)
                ≈ 0.5  → half-step jump       (delta = 10)
                ≈ 0.33 → jarring gap           (delta = 20)

D4_A range is ≈ [1, 20] (8 × ALPHA attractor harmonics); scale = 0.1.
"""
from __future__ import annotations

from collections import deque

import numpy as np


class ArcScorer:
    """Rolling buffer of recent D4_A values for transition quality scoring.

    Args:
        capacity: Maximum number of recent D4_A values to retain (default 16).
    """

    _D4A_NEUTRAL = 10.0   # midpoint of the [1, 20] basin range
    _SCALE       = 0.1    # delta=10 → score≈0.5

    def __init__(self, capacity: int = 16) -> None:
        self._buf: deque[float] = deque(maxlen=capacity)

    # ------------------------------------------------------------------
    # Feed
    # ------------------------------------------------------------------

    def push(self, d4_a: float | None) -> None:
        """Append the D4_A value of the track that just started playing.

        Args:
            d4_a: D4_A score, or ``None`` if not yet computed (silently ignored).
        """
        if d4_a is not None:
            self._buf.append(float(d4_a))

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def level(self) -> float:
        """Mean D4_A of the buffer; ``_D4A_NEUTRAL`` if empty."""
        return float(np.mean(self._buf)) if self._buf else self._D4A_NEUTRAL

    @property
    def slope(self) -> float:
        """Linear trend (D4_A units / track) over the last 8 buffered values.

        Positive slope → arc is building; negative → releasing.
        Returns 0.0 when fewer than 3 values are available.
        """
        if len(self._buf) < 3:
            return 0.0
        y = np.array(list(self._buf)[-8:], dtype=float)
        x = np.arange(len(y), dtype=float)
        return float(np.polyfit(x, y, 1)[0])

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score_candidate(self, d4_a: float) -> float:
        """Rate how smoothly *d4_a* continues the current arc.

        Args:
            d4_a: D4_A score of the candidate track.

        Returns:
            float in [0, 1]: 1.0 = perfect continuation, → 0 = jarring jump.
        """
        target = self.level + self.slope
        delta  = abs(d4_a - target)
        return 1.0 / (1.0 + delta * self._SCALE)

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._buf)

    def __repr__(self) -> str:
        return (
            f"ArcScorer(n={len(self._buf)}/{self._buf.maxlen}, "
            f"level={self.level:.2f}, slope={self.slope:+.3f})"
        )
