"""phi.models.coplay_rank — session co-play graph → phi_rank via PageRank.

Motivation
----------
phi_rank (weight 0.08 in the ranker) falls back to 0.5 for every track when
the torch OctopusTracer is not available.  This module computes a real score
from listening history alone:

    1. Sort played tracks by last_played timestamp.
    2. Tracks within SESSION_WINDOW positions of each other get a directed edge;
       weight = proximity × completion quality of each track.
    3. Power-iteration PageRank (d=0.85) over the undirected co-play graph.
    4. Min-max normalise to [0.10, 1.00] and write as "phi_rank" annotation.

Tracks that consistently *anchor* listening sessions — surrounded by other
tracks that also get completed — accumulate high centrality.  Skipped tracks
and tracks that appear in isolation stay near the floor.

Tracks with no play history receive no annotation and fall through to the
existing _phi_rank fallback of 0.5.

Checkpoint: ~/.phi/coplay_rank.json  (override: PHI_COPLAY_RANK)
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from phi.core.library import Library

from phi.core.ranker._constants import SESSION_WINDOW

_log = logging.getLogger("phi.coplay_rank")

COPLAY_DAMPING: float = 0.85
COPLAY_ITERATIONS: int = 50
COPLAY_FLOOR: float = 0.10       # min normalised score written to annotations
COPLAY_MAX_PLAYED: int = 2_000   # cap to keep adjacency matrix manageable

_DEFAULT_CKPT = Path.home() / ".phi" / "coplay_rank.json"
_LOCK = threading.Lock()


def _ckpt_path() -> Path:
    override = os.environ.get("PHI_COPLAY_RANK")
    return Path(override) if override else _DEFAULT_CKPT


# ── build adjacency ────────────────────────────────────────────────────────────

def _build_adjacency(
    played: list[tuple[str, str, float]],
    window: int,
) -> tuple[list[str], np.ndarray]:
    """Build undirected weighted adjacency matrix from play history.

    Parameters
    ----------
    played  : [(path, last_played_str, completion_rate)] sorted ascending by time
    window  : maximum positional distance for an edge

    Returns
    -------
    (paths, A)  where A[i, j] = cumulative co-play weight (float32, symmetric)
    """
    # Cap to most recent COPLAY_MAX_PLAYED tracks
    if len(played) > COPLAY_MAX_PLAYED:
        played = played[-COPLAY_MAX_PLAYED:]

    n = len(played)
    paths = [p for p, _, _ in played]
    rates = np.array([max(0.0, min(1.0, r)) for _, _, r in played], dtype=np.float32)

    A = np.zeros((n, n), dtype=np.float32)
    for i in range(n):
        for j in range(i + 1, min(i + window + 1, n)):
            # Proximity: 1/(j−i) — adjacent tracks strongest
            prox = 1.0 / float(j - i)
            # Quality: geometric mean of completion rates (penalises skips)
            q = float(np.sqrt(rates[i] * rates[j]))
            w = prox * q
            A[i, j] += w
            A[j, i] += w

    return paths, A


# ── PageRank ───────────────────────────────────────────────────────────────────

def _pagerank(A: np.ndarray, damping: float, iterations: int) -> np.ndarray:
    """Personalised PageRank via power iteration on adjacency *A*.

    A is symmetric non-negative; dangling nodes (zero column sum) teleport
    uniformly.  Returns a unit-L1 rank vector.
    """
    n = A.shape[0]
    col_sums = A.sum(axis=0)                     # (n,)
    dangling = col_sums == 0.0
    col_sums_safe = np.where(dangling, 1.0, col_sums)
    T = A / col_sums_safe[None, :]               # column-stochastic on non-dangling

    uniform = np.ones(n, dtype=np.float32) / n
    r = uniform.copy()
    for _ in range(iterations):
        # Dangling node mass redistributed uniformly
        dangling_mass = float(r[dangling].sum()) / n if dangling.any() else 0.0
        r = damping * (T @ r + dangling_mass) + (1.0 - damping) * uniform
    # Normalise to L1 = 1
    s = r.sum()
    if s > 0:
        r /= s
    return r


# ── CoPlayRanker ──────────────────────────────────────────────────────────────

class CoPlayRanker:
    """Compute phi_rank from listening co-play history via PageRank.

    Usage
    -----
    scores = CoPlayRanker().fit(library)
    CoPlayRanker.annotate(library, scores)
    """

    def __init__(
        self,
        window: int = SESSION_WINDOW,
        damping: float = COPLAY_DAMPING,
        iterations: int = COPLAY_ITERATIONS,
    ) -> None:
        self.window = window
        self.damping = damping
        self.iterations = iterations

    def fit(self, library: "Library") -> dict[str, float]:
        """Build co-play graph and return path → normalised PageRank score.

        Tracks with no play history are absent from the result dict; callers
        should default to 0.5 for missing keys.

        Returns {} when fewer than 3 tracks have been played.
        """
        # Collect and sort played tracks by timestamp
        played: list[tuple[str, str, float]] = []
        for path, stats in library.play_stats.items():
            ts = stats.get("last_played")
            if not ts or path not in library.meta_cache:
                continue
            rate = float(stats.get("completion_rate") or 0.5)
            played.append((path, str(ts), rate))

        if len(played) < 3:
            _log.info("CoPlayRanker.fit: fewer than 3 played tracks — skipping")
            return {}

        played.sort(key=lambda t: t[1])   # ascending by ISO timestamp

        paths, A = _build_adjacency(played, self.window)
        n = len(paths)

        if A.sum() == 0.0:
            _log.info("CoPlayRanker.fit: adjacency is all-zero (single session)")
            return {p: 0.5 for p in paths}

        r = _pagerank(A, self.damping, self.iterations)

        # Min-max normalise to [COPLAY_FLOOR, 1.0]
        r_min, r_max = float(r.min()), float(r.max())
        if r_max > r_min:
            r_norm = COPLAY_FLOOR + (1.0 - COPLAY_FLOOR) * (r - r_min) / (r_max - r_min)
        else:
            r_norm = np.full(n, 0.5, dtype=np.float32)

        scores = {paths[i]: round(float(r_norm[i]), 4) for i in range(n)}
        _log.info(
            "CoPlayRanker.fit: %d tracks  min=%.3f  max=%.3f  mean=%.3f",
            n, float(r_norm.min()), float(r_norm.max()), float(r_norm.mean()),
        )
        return scores

    @staticmethod
    def annotate(
        library: "Library",
        scores: dict[str, float],
        *,
        phi_rank_key: str = "phi_rank",
        overwrite: bool = False,
    ) -> int:
        """Write *scores* into library.annotations[path][phi_rank_key].

        Existing values are preserved unless *overwrite* is True.
        Returns the number of annotations written.
        """
        n = 0
        for path, score in scores.items():
            ann = library.annotations.setdefault(path, {})
            if overwrite or not ann.get(phi_rank_key):
                ann[phi_rank_key] = score
                n += 1
        _log.info("CoPlayRanker.annotate: wrote phi_rank for %d tracks", n)
        return n

    def fit_and_annotate(self, library: "Library", **kw) -> dict[str, float]:
        """Convenience: fit, annotate, and return scores."""
        scores = self.fit(library)
        if scores:
            self.annotate(library, scores, **kw)
        return scores

    # ── persistence ───────────────────────────────────────────────────────────

    @staticmethod
    def save(scores: dict[str, float], path: str | Path | None = None) -> None:
        """Save scores dict to JSON checkpoint."""
        p = Path(path) if path else _ckpt_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(scores, indent=2), encoding="utf-8")
        _log.info("CoPlayRanker.save → %s  (%d entries)", p, len(scores))

    @staticmethod
    def load(path: str | Path | None = None) -> dict[str, float] | None:
        """Load a previously saved scores dict, or None if absent / corrupt."""
        p = Path(path) if path else _ckpt_path()
        if not p.exists():
            return None
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return None
            return {str(k): float(v) for k, v in raw.items()}
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            _log.warning("CoPlayRanker.load failed: %s", exc)
            return None


# ── module-level helper (mirrors _embed.py pattern) ───────────────────────────

_fitted: bool = False
_fit_lock = threading.Lock()


def maybe_rank_and_annotate(library: "Library") -> bool:
    """Fit CoPlayRanker, annotate the library, and save the checkpoint.

    Idempotent — returns True immediately on subsequent calls.
    Safe to call from a background thread alongside maybe_fit_and_annotate.

    Returns True on success, False on any error.
    """
    global _fitted
    with _fit_lock:
        if _fitted:
            return True

    try:
        ranker = CoPlayRanker()
        scores = ranker.fit(library)
        if scores:
            ranker.annotate(library, scores)
            try:
                CoPlayRanker.save(scores)
            except Exception as exc:
                _log.warning("CoPlayRanker.save failed: %s", exc)
        with _fit_lock:
            _fitted = True
        return True
    except Exception as exc:
        _log.warning("maybe_rank_and_annotate failed: %s", exc)
        return False


def refetch_coplay() -> None:
    """Reset the singleton (for tests / forced refit)."""
    global _fitted
    with _fit_lock:
        _fitted = False
