"""Learn ranker WEIGHTS from skip / complete via exponentiated gradient.

Stays on the simplex: weights > LEARN_W_MIN and sum to 1.
Checkpoint: ~/.phi/ranker_weights.json (override with PHI_RANKER_WEIGHTS).
"""
from __future__ import annotations

import json
import math
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from ._constants import (
    IMPLICIT_NEGATIVE_THRESHOLD,
    IMPLICIT_POSITIVE_THRESHOLD,
    LEARN_ETA,
    LEARN_W_MIN,
    WEIGHT_KEYS,
    WEIGHTS,
)
from ._scoring import (
    _elo_normalised,
    _genre_affinity,
    _mood_affinity,
    _novelty_score,
    _phi_rank,
)
from ._session import RankContext

if TYPE_CHECKING:
    from phi.core.library import Library

_lock = threading.Lock()
_learned: dict[str, float] | None = None


def _ckpt_path() -> Path:
    override = os.environ.get("PHI_RANKER_WEIGHTS")
    if override:
        return Path(override)
    return Path.home() / ".phi" / "ranker_weights.json"


def _normalise(w: dict[str, float]) -> dict[str, float]:
    clipped = {k: max(LEARN_W_MIN, float(w.get(k, WEIGHTS[k]))) for k in WEIGHT_KEYS}
    total = sum(clipped.values())
    if total <= 0:
        return dict(WEIGHTS)
    return {k: v / total for k, v in clipped.items()}


def _load() -> dict[str, float] | None:
    path = _ckpt_path()
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None
        return _normalise(raw)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _save(w: dict[str, float]) -> None:
    path = _ckpt_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(w, indent=2), encoding="utf-8")
    except OSError:
        pass


def has_checkpoint() -> bool:
    return _ckpt_path().exists()


def reset_learned() -> None:
    """Drop in-memory weights (tests). Disk checkpoint is left alone."""
    global _learned
    with _lock:
        _learned = None


def active_weights() -> dict[str, float]:
    """Learned simplex, or the hardcoded WEIGHTS prior."""
    global _learned
    with _lock:
        if _learned is None:
            _learned = _load() or dict(WEIGHTS)
        return dict(_learned)


def dimension_scores(
    path: str,
    library: "Library",
    ctx: RankContext,
) -> dict[str, float]:
    """Five ranker dimensions in [0, 1] for *path* under *ctx*."""
    meta = library.meta_cache.get(path) or {}
    ann = library.annotations.get(path) or {}
    stats = library.play_stats.get(path) or {}
    return {
        "genre": _genre_affinity(meta, ann, ctx),
        "mood": _mood_affinity(ann, meta, ctx),
        "novelty": _novelty_score(stats),
        "elo": _elo_normalised(library.get_elo(path)),
        "phi_rank": _phi_rank(ann),
    }


def update_from_feedback(features: dict[str, float], y: float) -> dict[str, float]:
    """One EG step. *y* = +1 complete, −1 skip. Returns the new simplex."""
    global _learned
    w = active_weights()
    for k in WEIGHT_KEYS:
        x = max(0.0, min(1.0, float(features.get(k, 0.0))))
        w[k] *= math.exp(LEARN_ETA * y * x)
    w = _normalise(w)
    with _lock:
        _learned = w
        _save(w)
    return dict(w)


def observe_departure(path: str, library: "Library") -> dict[str, float] | None:
    """Update weights from this track's completion_rate. None if ambiguous."""
    stats = library.play_stats.get(path) or {}
    completion = stats.get("completion_rate")
    if completion is None:
        return None
    if completion >= IMPLICIT_POSITIVE_THRESHOLD:
        y = 1.0
    elif completion < IMPLICIT_NEGATIVE_THRESHOLD:
        y = -1.0
    else:
        return None
    ctx = RankContext.from_library(library, current_path=None, exclude=path)
    feats = dimension_scores(path, library, ctx)
    return update_from_feedback(feats, y)


def fit_from_play_stats(library: "Library") -> int:
    """Replay stored completion_rate as EG updates. Returns number of steps."""
    rows: list[tuple[str, str]] = []
    for path, stats in library.play_stats.items():
        if path not in library.meta_cache:
            continue
        rate = stats.get("completion_rate")
        if rate is None:
            continue
        if rate >= IMPLICIT_POSITIVE_THRESHOLD or rate < IMPLICIT_NEGATIVE_THRESHOLD:
            rows.append((str(stats.get("last_played") or ""), path))
    rows.sort()
    n = 0
    for _, path in rows:
        if observe_departure(path, library) is not None:
            n += 1
    return n
