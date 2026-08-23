# -*- coding: utf-8 -*-
"""phi.engine.arc_engine — Session Arc Engine.

Maintains a target D4_A trajectory (the "arc") for the current session and
picks the next track from the library to keep playback on that trajectory.

Arc shapes
----------
FLAT    — constant energy (D4_A stays near the middle of the range)
RISING  — energy climbs linearly over the session horizon
FALLING — energy falls linearly
PEAK    — rises to a peak at the halfway point then decays (parabola)
VALLEY  — inverse of PEAK — dip then recovery
WAVE    — one full sinusoidal oscillation over the horizon

D4_A values are normalised to [0, 1] (per-segment, pre-computed at init)
so all arc targets and candidate scores live in the same unit interval.

Usage::

    engine = ArcEngine(depth=8)
    engine.shape  = ArcShape.RISING
    engine.active = True
    # on every track change (CAIRRN-informed):
    suggestion = engine.pick_next(
        current_path, library, meta_cache, walker,
        zone_map=zone_map, transition_matrix=T,
        ring_activations=harmonic_index.activation_vector(),
    )
    # → path str or None; pass to on_play_next_path() to pre-queue it
    # Coherence-driven alpha: ring diffuse → arc shape leads;
    #                         ring locked  → CAIRRN zone transition leads.
"""
from __future__ import annotations

import enum
import math
import logging
from typing import TYPE_CHECKING

import numpy as np

from phi.models.dragon_curve import DragonCurve

if TYPE_CHECKING:
    from phi.meta.cache import MetaCache
    from phi.core.library import Library
    from phi.engine.curve_walker import CurveWalker

log = logging.getLogger("phi.arc_engine")

# ── Arc shapes ────────────────────────────────────────────────────────────────

class ArcShape(enum.Enum):
    FLAT    = "flat"
    RISING  = "rising"
    FALLING = "falling"
    PEAK    = "peak"
    VALLEY  = "valley"
    WAVE    = "wave"


# ── ArcEngine ─────────────────────────────────────────────────────────────────

class ArcEngine:
    """Session arc planner — picks the next track to hit a D4_A target.

    Args:
        depth:   Dragon-curve fold depth (must match canvas + CurveWalker).
        horizon: Number of tracks that make up one full arc cycle.
        k:       Scoring sharpness — larger = prefer tracks closer to target.
        pool:    Top-N candidates to sample from (adds diversity).
    """

    def __init__(
        self,
        depth:   int   = 8,
        horizon: int   = 20,
        k:       float = 20.0,
        pool:    int   = 6,
    ) -> None:
        self._dc      = DragonCurve(depth)
        self.shape    = ArcShape.FLAT
        self.active   = False
        self.horizon  = horizon
        self._k       = k
        self._pool    = pool
        self._step    = 0   # tracks played since arc mode was activated

        # Pre-compute normalised D4_A for every segment ─────────────────────
        pts   = self._dc._points            # (n_segs+1, 2)
        n     = self._dc.n_segments         # 256 for depth=8
        D1    = pts[1:] - pts[:-1]          # (n, 2)
        nxt   = np.minimum(np.arange(n) + 1, n - 1)
        mid_n = (pts[nxt] + pts[nxt + 1]) / 2.0   # (n, 2)
        D2    = mid_n[:, 1]                 # (n,)
        D3    = pts[nxt + 1]                # (n, 2)
        n1    = np.linalg.norm(D1, axis=1)
        d4a   = np.where(n1 > 1e-9, np.linalg.norm(D3, axis=1) / n1 - D2, 0.0)
        lo, hi = float(d4a.min()), float(d4a.max())
        rng   = max(hi - lo, 1e-9)
        self._d4a_norm    = ((d4a - lo) / rng).astype(np.float32)   # (n,) ∈ [0,1]
        self._d4a_lo      = lo
        self._d4a_range   = rng

        log.debug(
            "ArcEngine ready  n_segs=%d  D4_A [%.2f, %.2f]  horizon=%d",
            n, lo, hi, horizon,
        )

    # ── Arc target ────────────────────────────────────────────────────────────

    def target(self, step: int | None = None) -> float:
        """Return the target normalised D4_A in [0, 1] for the given step.

        If *step* is None, uses the internal ``_step`` counter.
        """
        s = self._step if step is None else step
        t = min(1.0, s / max(1, self.horizon))
        sh = self.shape
        if sh == ArcShape.FLAT:
            return 0.5
        if sh == ArcShape.RISING:
            return t
        if sh == ArcShape.FALLING:
            return 1.0 - t
        if sh == ArcShape.PEAK:
            return 4.0 * t * (1.0 - t)          # parabola, peaks at t=0.5
        if sh == ArcShape.VALLEY:
            return 1.0 - 4.0 * t * (1.0 - t)
        if sh == ArcShape.WAVE:
            return 0.5 + 0.5 * math.sin(2.0 * math.pi * t)
        return 0.5

    # ── Track scoring ─────────────────────────────────────────────────────────

    def d4a_norm_for_seg(self, seg: int) -> float:
        """Normalised [0, 1] D4_A for a curve segment index."""
        return float(self._d4a_norm[seg % len(self._d4a_norm)])

    # ── Next-track selection ──────────────────────────────────────────────────

    # ── CAIRRN coherence ─────────────────────────────────────────────────────

    @staticmethod
    def _ring_coherence(activations: np.ndarray) -> float:
        """
        Measure how concentrated the harmonic ring activation is.

        Coherence = 1 − normalised Shannon entropy of the softmax distribution.

        Returns a value in [0, 1]:
            0.0  — activations are perfectly uniform (ring is diffuse, arc leads)
            1.0  — all activation is on one shard (ring is locked, CAIRRN leads)

        A fully uniform distribution over 8 shards has entropy = log(8).
        We normalise by log(8) so the result is always in [0, 1].
        """
        if activations is None or len(activations) == 0:
            return 0.0
        # Softmax — stabilised
        a = activations - activations.max()
        p = np.exp(a)
        p /= p.sum()
        # Shannon entropy, clamped against log(0)
        entropy = -float(np.sum(p * np.log(np.maximum(p, 1e-12))))
        max_entropy = math.log(len(p))          # log(8) ≈ 2.079
        return 1.0 - (entropy / max_entropy if max_entropy > 0 else 0.0)

    # ── Next-track selection ──────────────────────────────────────────────────

    def pick_next(
        self,
        current_path: str,
        library:      "Library",
        meta_cache:   "MetaCache",
        walker:       "CurveWalker",
        exclude:            set[str] | None  = None,
        zone_map:           dict[str, int]   | None = None,
        transition_matrix:  np.ndarray       | None = None,
        ring_activations:   np.ndarray       | None = None,
    ) -> str | None:
        """Pick the best next track to follow the arc, optionally steered by
        the live CAIRRN ring state.

        **Arc scoring** (always active):
            Each candidate is scored by Gaussian proximity to the arc's
            next-step D4_A target.  This ensures the session follows the
            chosen shape (FLAT/RISING/PEAK/WAVE/…).

        **CAIRRN blending** (active when zone_map + T + ring are provided):
            A second score reflects how likely a zone transition is given the
            ring's current activation state.  The two scores are combined with
            a coherence-driven alpha:

                alpha = ring_coherence(activations)      # ∈ [0, 1]
                score = (1 − alpha) · arc_score  +  alpha · cairrn_score

            When the ring is diffuse (alpha ≈ 0) the arc shape dominates.
            When the ring is locked into one zone (alpha ≈ 1) CAIRRN steers
            toward a musically natural zone transition.

        Args:
            current_path:       Path of the track currently playing (excluded).
            library:            App-wide Library.
            meta_cache:         App-wide MetaCache.
            walker:             Shared CurveWalker (provides segment map).
            exclude:            Additional paths to skip (e.g. recently played).
            zone_map:           {path: zone_id (0–7)} from ZoneClusterer.
            transition_matrix:  (8, 8) row-normalised P(zone_j | zone_i).
            ring_activations:   (8,) float array from HarmonicIndex.activation_vector().

        Returns:
            Absolute path of the suggested next track, or None if the library
            is empty or all tracks are excluded.
        """
        if not self.active:
            return None

        tgt = self.target()   # where D4_A should be at step+1

        # Build segment map for all library tracks (vectorised, <5 ms for 7k)
        seg_map = walker.seg_map(library, meta_cache)

        excl = {current_path} | (exclude or set())
        candidates = [p for p in library.playlist if p not in excl]
        if not candidates:
            return None

        # ── Arc score (Gaussian proximity to D4_A target) ─────────────────────
        segs   = np.array([seg_map.get(p, 0) for p in candidates], dtype=np.int32)
        d4a_n  = self._d4a_norm[segs]                              # (N,) ∈ [0, 1]
        arc_scores = 1.0 / (1.0 + self._k * (d4a_n - tgt) ** 2)  # (N,) ∈ (0, 1]

        scores = arc_scores   # default: pure arc

        # ── CAIRRN blend ──────────────────────────────────────────────────────
        _use_cairrn = (
            zone_map is not None
            and transition_matrix is not None
            and ring_activations is not None
            and len(ring_activations) == 8
        )
        alpha = 0.0
        if _use_cairrn:
            alpha = self._ring_coherence(ring_activations)

            if alpha > 1e-3:
                # Current zone for weighting T rows
                current_zone = zone_map.get(current_path, -1)  # type: ignore[union-attr]

                # Softmax of ring activations → probability over zones
                a = ring_activations - ring_activations.max()   # type: ignore[union-attr]
                ring_p = np.exp(a)
                ring_p /= ring_p.sum()                          # (8,) P(zone)

                # Candidate zone ids
                zone_ids = np.array(
                    [zone_map.get(p, -1) for p in candidates],  # type: ignore[union-attr]
                    dtype=np.int32,
                )

                # For each candidate: P(ring activates its zone) × P(transition)
                cairrn_scores = np.ones(len(candidates), dtype=np.float64)
                for i, (path, zid) in enumerate(zip(candidates, zone_ids)):
                    if zid < 0:
                        continue
                    ring_w = float(ring_p[zid])
                    trans_w = (
                        float(transition_matrix[current_zone, zid])  # type: ignore[index]
                        if 0 <= current_zone < 8
                        else float(ring_p[zid])
                    )
                    cairrn_scores[i] = ring_w * trans_w

                # Normalise to [0, 1]
                cs_max = cairrn_scores.max()
                if cs_max > 1e-9:
                    cairrn_scores /= cs_max

                scores = (1.0 - alpha) * arc_scores + alpha * cairrn_scores

        # ── Sample from top-pool candidates ───────────────────────────────────
        n_pool  = min(self._pool, len(candidates))
        top_idx = np.argpartition(scores, -n_pool)[-n_pool:]
        top_s   = scores[top_idx].astype(np.float64)
        top_s  /= top_s.sum()
        chosen  = int(np.random.choice(top_idx, p=top_s))
        path    = candidates[chosen]

        log.debug(
            "ArcEngine.pick_next  step=%d  tgt=%.3f  alpha=%.2f  "
            "d4a_norm=%.3f  path=…%s",
            self._step, tgt, alpha, float(d4a_n[chosen]), path[-40:],
        )
        return path

    def on_track_played(self) -> None:
        """Increment the internal step counter (call after each track change)."""
        self._step += 1

    def reset(self) -> None:
        """Reset step counter (call when arc mode is activated fresh)."""
        self._step = 0
