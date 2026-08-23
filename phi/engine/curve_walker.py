# -*- coding: utf-8 -*-
"""phi.engine.curve_walker — CurveWalker: sort the queue by dragon-curve position.

Every track gets a segment index (0 … n_segments-1) that represents where it
sits along the dragon-curve path.  Sorting the queue by this index produces a
"curve walk": a continuous traversal from one end of the curve to the other,
moving through the library in order of musical character (BPM × Key projection
space).

Segment assignment priority
---------------------------
1. ``clipper_x / clipper_y`` from the annotations table (set by the anchor
   workflow or BPM×Key auto-compute).
2. BPM × Key projection from the in-memory ``Library.meta_cache`` dict
   (populated by MetaWorker — no disk hit).
3. Centre of the unit square (segment nearest to (0.5, 0.5)) — silent fallback
   for tracks with no metadata at all.

The vectorised core in ``_seg_indices`` processes all N library tracks in a
single (N × M) numpy matrix operation (M = n_segments = 256 for depth=8),
completing in <10 ms for a library of 10 000 tracks.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from phi.models.dragon_curve import DragonCurve
from phi.ui.qt.rooms.dragon_room import bpm_key_to_unit   # pure function, no Qt

if TYPE_CHECKING:
    from phi.meta.cache import MetaCache
    from phi.core.library import Library

log = logging.getLogger("phi.curve_walker")


class CurveWalker:
    """Maps library tracks to dragon-curve segment positions and sorts the queue.

    Args:
        depth: Dragon-curve fold depth (must match the UI canvas depth=8).
    """

    def __init__(self, depth: int = 8) -> None:
        self._dc = DragonCurve(depth)
        log.debug("CurveWalker ready  depth=%d  n_segs=%d", depth, self._dc.n_segments)

    # ── shared core ───────────────────────────────────────────────────────────

    def _seg_indices(
        self,
        library:    "Library",
        meta_cache: "MetaCache",
    ) -> tuple[list[str], np.ndarray]:
        """Compute segment index for every library track.

        Returns:
            (paths, seg_idx)  where seg_idx[i] is the curve segment for
            paths[i], shape (N,), dtype int32.
        """
        paths = library.playlist
        N     = len(paths)
        if N == 0:
            return [], np.empty(0, dtype=np.int32)

        # Bulk fetch anchored annotations (expression index → <5 ms)
        anchored: dict = {}
        try:
            anchored = meta_cache.get_anchored_annotations("clipper_x") or {}
        except Exception:
            pass

        lib_meta: dict = getattr(library, "meta_cache", {})

        xs = np.empty(N, dtype=np.float64)
        ys = np.empty(N, dtype=np.float64)
        for i, path in enumerate(paths):
            ann = anchored.get(path)
            if ann:
                xs[i] = float(ann.get("clipper_x", 0.5))
                ys[i] = float(ann.get("clipper_y", 0.5))
            else:
                meta = lib_meta.get(path) or {}
                bpm  = meta.get("bpm")
                key  = meta.get("key") or meta.get("key_sig")
                xs[i], ys[i] = bpm_key_to_unit(bpm, key)

        # Unit-square → curve coordinate space
        bb_min   = self._dc._bb_min
        bb_range = self._dc._bb_range
        xy_c = np.column_stack([
            bb_min[0] + xs * bb_range[0],
            bb_min[1] + ys * bb_range[1],
        ])   # (N, 2)

        # Vectorised nearest-segment: (N, M, 2) → (N, M) → argmin → (N,)
        diff    = xy_c[:, None, :] - self._dc._seg_mids[None, :, :]
        seg_idx = np.argmin((diff ** 2).sum(axis=2), axis=1).astype(np.int32)
        return paths, seg_idx

    # ── public API ────────────────────────────────────────────────────────────

    def build_order(
        self,
        library:    "Library",
        meta_cache: "MetaCache",
    ) -> list[int]:
        """Return playlist indices sorted by curve-walk position.

        Returns:
            list[int] — playlist indices in curve-walk order (index 0 = curve
            start, index -1 = curve end).  All library tracks are included.
        """
        paths, seg_idx = self._seg_indices(library, meta_cache)
        if len(paths) == 0:
            return []
        order = np.argsort(seg_idx, kind="stable")
        log.debug(
            "CurveWalker.build_order: N=%d  seg range [%d, %d]",
            len(paths), int(seg_idx.min()), int(seg_idx.max()),
        )
        return order.tolist()

    def seg_map(
        self,
        library:    "Library",
        meta_cache: "MetaCache",
    ) -> dict[str, int]:
        """Return {path: segment_index} for all library tracks.

        Used by ArcEngine to vectorise candidate scoring without per-track
        attribute lookups.
        """
        paths, seg_idx = self._seg_indices(library, meta_cache)
        return {p: int(seg_idx[i]) for i, p in enumerate(paths)}

    def segment_for(
        self,
        path:       str,
        meta_cache: "MetaCache",
        library:    "Library",
    ) -> int:
        """Segment index for a single track (used for per-track queries).

        Returns:
            int in [0, n_segments - 1].
        """
        ann: dict = {}
        try:
            ann = meta_cache.get_annotation(path) or {}
        except Exception:
            pass

        x_n = ann.get("clipper_x")
        y_n = ann.get("clipper_y")

        if x_n is None or y_n is None:
            lib_meta: dict = getattr(library, "meta_cache", {})
            meta = lib_meta.get(path) or {}
            bpm  = meta.get("bpm")
            key  = meta.get("key") or meta.get("key_sig")
            x_n, y_n = bpm_key_to_unit(bpm, key)

        cx, cy = self._dc.unit_to_curve(float(x_n), float(y_n))
        return self._dc.nearest_segment(cx, cy)
