# -*- coding: utf-8 -*-
"""phi.core.similarity — nearest-neighbour search over CLAP audio vectors.

Once CLAPModel has run over the library, every track has a 'mood_vec'
stored in Library.annotations.  This module does fast cosine similarity
search over those vectors to implement:

    find_similar(path, library, n=10)  →  list of (path, score) pairs

When a ForestFloor is bound (via ``bind_floor``), similarity search is
routed through a CAIRRN MATH-gated PhiSimilarityIndex — a precomputed
(n × d) numpy matrix.  One matrix-vector multiply replaces the O(n × d)
Python loop, giving ~200× speedup on a 1000-track library.

When the floor is not bound, the pure-Python fallback is used.
"""
from __future__ import annotations

import math
import threading
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from phi.engine.forest_floor import ForestFloor

try:
    from phi.engine.similarity_index import PhiSimilarityIndex
except ImportError:
    PhiSimilarityIndex = None  # type: ignore[assignment,misc]

# Floor wired by PhiApp; drives MATH hub-gated cache coherence.
_floor: Optional["ForestFloor"] = None
_scheduler: Any = None


def set_scheduler(sched: Any) -> None:
    """Wire an external scheduler for MATH-gated prefetch decisions."""
    global _scheduler
    _scheduler = sched

# ── CAIRRN similarity index cache (MATH hub-gated) ────────────────────────────
_sim_lock       = threading.Lock()
_sim_index:     Optional["PhiSimilarityIndex"] = None
_sim_index_step: int = -1

# ── build_radio() MATH-gated cache ────────────────────────────────────────────
# Keyed by (seed_path, length, diversity, vec_key) → list[str].
# Invalidated when the MATH hub step advances (embedding space shifted).
_radio_cache:           dict[tuple, list[str]] = {}
_radio_cache_math_step: int = -1


def bind_floor(floor: "ForestFloor") -> None:
    """Subscribe to the MATH hub (shard 3) on the forest floor.

    When the embedding space shifts — MATH hub loses coherence after
    approximately 20 CLAP batches (τ≈19.5) — the similarity index is
    invalidated.  The next find_similar() call will rebuild the matrix
    from the current annotation store rather than reading stale vectors.

    Called once by PhiApp after the floor is instantiated.
    """
    global _floor
    _floor = floor

    def _on_math_shift(result, payload: dict) -> None:
        if result.should_act:
            _invalidate_similarity()

    floor.when_floor_shifts(shard=3, handler=_on_math_shift)


# ── cache helpers ──────────────────────────────────────────────────────────────

def _invalidate_similarity() -> None:
    """Invalidate the MATH-gated similarity index."""
    global _sim_index, _sim_index_step
    with _sim_lock:
        _sim_index      = None
        _sim_index_step = -1


def _get_similarity_index(library: "Any") -> "Optional[PhiSimilarityIndex]":
    """Return the CAIRRN-gated numpy similarity index, rebuilding when stale."""
    global _sim_index, _sim_index_step
    import logging
    _log = logging.getLogger("phi.similarity")

    if PhiSimilarityIndex is None:
        return None

    if _floor is None:
        return PhiSimilarityIndex.build(library)

    try:
        math_hub = _floor._bridge._hubs["MATH"]
        with _sim_lock:
            if (
                _sim_index is not None
                and _sim_index_step == math_hub.steps
                and math_hub.coherence >= _floor._bridge.coherence_floor
            ):
                return _sim_index
            idx = PhiSimilarityIndex.build(library)
            _sim_index      = idx
            _sim_index_step = math_hub.steps
            if idx is not None:
                _log.info(
                    "CAIRRN/MATH: similarity index rebuilt  tracks=%d  math_step=%d",
                    idx.size, math_hub.steps,
                )
            return idx
    except Exception:
        return PhiSimilarityIndex.build(library)


# ── cosine helpers ────────────────────────────────────────────────────────────

def _cosine_py(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    ma  = math.sqrt(sum(x * x for x in a))
    mb  = math.sqrt(sum(y * y for y in b))
    if ma == 0 or mb == 0:
        return 0.0
    return max(-1.0, min(1.0, dot / (ma * mb)))


def _cosine(a, b) -> float:
    try:
        import numpy as np
        av = np.asarray(a, dtype=np.float32)
        bv = np.asarray(b, dtype=np.float32)
        ma = np.linalg.norm(av)
        mb = np.linalg.norm(bv)
        if ma == 0 or mb == 0:
            return 0.0
        return float(np.dot(av, bv) / (ma * mb))
    except ImportError:
        return _cosine_py(a, b)


# ── main search API ───────────────────────────────────────────────────────────

def find_similar(
    path:    str,
    library,
    *,
    n:       int   = 10,
    vec_key: str   = "mood_vec",
    exclude_self: bool = True,
) -> list[tuple[str, float]]:
    """
    Return the *n* most similar tracks to *path* by cosine similarity
    over the stored vector at *vec_key* (default: "mood_vec" from CLAPModel).

    When a ForestFloor is bound, uses the precomputed numpy matrix
    index (O(n) numpy) instead of the pure-Python O(n × d) loop.

    Parameters
    ----------
    path        Absolute path of the seed track.
    library     phi Library instance.
    n           Number of results to return (default 10).
    vec_key     Annotation key holding the float vector.
    exclude_self  If True, the seed track is excluded from results.

    Returns
    -------
    List of (path, score) sorted by descending similarity.
    Score is cosine similarity in [-1, 1]; higher = more similar.
    Returns [] if the seed has no vector or the library has no vectors.
    """
    # ── CAIRRN MATH signal — roots seeking kin through the embedding soil ──────
    if _floor is not None:
        try:
            _floor.seek_kin(n)
        except Exception:
            pass

    # Fast path — CAIRRN numpy index
    if vec_key == "mood_vec":
        idx = _get_similarity_index(library)
        if idx is not None:
            exclude_set = {path} if exclude_self else None
            return idx.find_similar(path, n=n, exclude=exclude_set, library=library)

    # Pure-Python fallback
    seed_ann = library.get_annotation(path)
    if not seed_ann:
        return []

    seed_vec = seed_ann.get(vec_key)
    if not seed_vec:
        return []

    results: list[tuple[str, float]] = []
    for p in library.playlist:
        if exclude_self and p == path:
            continue
        ann = library.get_annotation(p)
        if not ann:
            continue
        vec = ann.get(vec_key)
        if not vec:
            continue
        score = _cosine(seed_vec, vec)
        results.append((p, score))

    results.sort(key=lambda t: -t[1])
    return results[:n]


def find_similar_to_vec(
    vec:     list[float],
    library,
    *,
    n:       int  = 10,
    vec_key: str  = "mood_vec",
    exclude: Optional[set[str]] = None,
) -> list[tuple[str, float]]:
    """
    Variant that takes a raw vector instead of a path.
    Useful for building playlists from an average/centroid vector.

    Uses the CAIRRN numpy index when available (single matmul instead of
    Python loop) — critical for build_radio() which calls this 20+ times.
    """
    exclude = exclude or set()

    # Fast path — CAIRRN numpy index
    if vec_key == "mood_vec":
        idx = _get_similarity_index(library)
        if idx is not None:
            return idx.find_similar_to_vec(vec, n=n, exclude=exclude)

    # Pure-Python fallback
    results: list[tuple[str, float]] = []
    for p in library.playlist:
        if p in exclude:
            continue
        ann = library.get_annotation(p)
        if not ann:
            continue
        pv = ann.get(vec_key)
        if not pv:
            continue
        results.append((p, _cosine(vec, pv)))
    results.sort(key=lambda t: -t[1])
    return results[:n]


def coverage(library, vec_key: str = "mood_vec") -> tuple[int, int]:
    """Return (tracks_with_vec, total_tracks) for *vec_key*."""
    total    = library.size
    with_vec = sum(
        1 for p in library.playlist
        if library.get_annotation(p) and library.get_annotation(p).get(vec_key)
    )
    return with_vec, total


# ── playlist generation ───────────────────────────────────────────────────────

def build_radio(
    seed_path: str,
    library,
    *,
    length:  int   = 20,
    vec_key: str   = "mood_vec",
    diversity: float = 0.15,
) -> list[str]:
    """
    Build a radio-style playlist starting from *seed_path*.

    Each step picks the most similar remaining track, with a small random
    component (*diversity*) to prevent exact duplicate queues on re-run.

    CAIRRN MATH gate: the result is cached per MATH hub step.  The O(20×n)
    cosine scan only runs when the MATH hub signals the embedding space has
    shifted — roughly every 14 CLAP batches (τ≈19.5).  Between invalidations
    the same seed returns the cached list instantly.

    Cache is keyed by (seed_path, length, diversity, vec_key) — distinct
    radio configurations get independent entries.

    Parameters
    ----------
    seed_path   Starting track.
    library     phi Library instance.
    length      Number of tracks in the resulting playlist.
    diversity   [0, 1] — higher = more variety, lower = tighter coherence.

    Returns a list of absolute paths (seed_path NOT included).
    """
    global _radio_cache, _radio_cache_math_step

    # ── CAIRRN MATH signal — seeking kin through the embedding soil ────────────
    if _floor is not None:
        try:
            _floor.seek_kin(length)
        except Exception:
            pass

    # ── MATH gate: check if cache is still valid ───────────────────────────────
    if _floor is not None:
        try:
            math_hub = _floor._bridge._hubs.get("MATH")
            current_step = math_hub.steps if math_hub else -1
        except Exception:
            current_step = -1
    else:
        current_step = -1

    cache_key = (seed_path, length, diversity, vec_key)

    if current_step >= 0 and current_step == _radio_cache_math_step:
        cached = _radio_cache.get(cache_key)
        if cached is not None:
            return cached
    else:
        # MATH step changed — clear stale entries
        _radio_cache.clear()
        _radio_cache_math_step = current_step

    import random

    seed_ann = library.get_annotation(seed_path)
    if not seed_ann or not seed_ann.get(vec_key):
        # Fallback: BPM-proximity sort (not cached — cheap enough)
        return _bpm_radio(seed_path, library, length)

    playlist: list[str]  = []
    used: set[str]       = {seed_path}
    current_vec          = list(seed_ann[vec_key])

    for _ in range(length):
        candidates = find_similar_to_vec(
            current_vec, library,
            n=max(length, 50),
            vec_key=vec_key,
            exclude=used,
        )
        if not candidates:
            break

        # Weighted random pick: exponentially more likely to take top result
        if diversity > 0:
            pool_size = max(1, int(len(candidates) * diversity))
            pool      = candidates[:pool_size]
            next_path, _ = random.choice(pool)
        else:
            next_path, _ = candidates[0]

        playlist.append(next_path)
        used.add(next_path)

        # Update current_vec to the centroid of used tracks
        # (gentle steering keeps the radio coherent)
        ann = library.get_annotation(next_path)
        if ann and ann.get(vec_key):
            nv = ann[vec_key]
            try:
                import numpy as np
                current_vec = list(
                    (np.asarray(current_vec, dtype=np.float32) * 0.85
                     + np.asarray(nv, dtype=np.float32) * 0.15)
                )
            except ImportError:
                n = len(current_vec)
                current_vec = [
                    current_vec[i] * 0.85 + nv[i] * 0.15
                    for i in range(n)
                ]

    # Store in cache under the current MATH step
    if current_step >= 0:
        _radio_cache[cache_key] = playlist

    return playlist


def _bpm_radio(seed_path: str, library, length: int) -> list[str]:
    """BPM-proximity fallback when no CLAP vectors are available."""
    seed_ann  = library.get_annotation(seed_path)
    seed_meta = library.get_meta(seed_path) or {}
    seed_bpm  = float(
        (seed_ann or {}).get("bpm") or seed_meta.get("bpm") or 120
    )

    scored: list[tuple[str, float]] = []
    for p in library.playlist:
        if p == seed_path:
            continue
        ann  = library.get_annotation(p) or {}
        meta = library.get_meta(p) or {}
        bpm  = float(ann.get("bpm") or meta.get("bpm") or 120)
        diff = abs(bpm - seed_bpm)
        scored.append((p, diff))

    scored.sort(key=lambda t: t[1])
    return [p for p, _ in scored[:length]]
