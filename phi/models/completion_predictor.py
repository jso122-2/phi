"""phi.models.completion_predictor — session-contextual completion predictor.

Architecture
------------
Ridge regression (sklearn) trained on every historical (context, track) → completion_rate
observation from Library.play_stats.  At session restore, predicts completion_rate for
every track in the library under the *current* session context and writes the result as
"predicted_completion" annotation.

TrackRanker.score() always computes the helm mix and blends
``predicted_completion`` as a buoyancy-scaled prior (not a bypass).

Feature vector (11 dimensions)
-------------------------------
0  genre_dot        cosine(track_genre_vec, session_genre_vec)  — 0.5 when either missing
1  mood_dot         cosine(track_mood_vec,  session_mood_vec)   — 0.5 when either missing
2  genre_norm       ||track_genre_vec||₂  — 0 when missing (tag richness signal)
3  mood_norm        ||track_mood_vec||₂   — 0 when missing
4  novelty_score    freshness ∈ [0, 1] from half-life decay
5  elo_norm         ELO mapped to [0, 1]
6  phi_rank         co-play PageRank ∈ [COPLAY_FLOOR, 1.0], or 0.5
7  skip_pressure    skip_count / plays ∈ [0, 1]
8  plays_log        log(plays + 1)
9  tod_sin          sin(2π × hour / 24)  — cyclic time encoding
10 tod_cos          cos(2π × hour / 24)

Training
--------
Rows are built by replaying the play history in chronological order.  For each
played track at position i, the session context is the mean genre_vec / mood_vec
of the preceding SESSION_WINDOW tracks.  Target = completion_rate.

Alpha is selected automatically via generalised cross-validation over RIDGE_ALPHAS
(default 0.01 → 1000).  The chosen value is logged and saved to the checkpoint
so you can inspect which regularisation strength the data preferred.

Minimum 30 labelled rows required; returns False and leaves annotations unchanged
when the library has too few plays.

Checkpoint: ~/.phi/completion_predictor.npz  (override: PHI_CP_CKPT)
"""
from __future__ import annotations

import logging
import math
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from phi.core.library import Library

from phi.core.ranker._constants import (
    ELO_NORM_HI,
    ELO_NORM_LO,
    NOVELTY_HALF_LIFE,
    NOVELTY_NEVER_HEARD,
    SESSION_WINDOW,
)

_log = logging.getLogger("phi.completion_predictor")

N_FEATURES: int = 11
MIN_SAMPLES: int = 30
# Search grid for cross-validated alpha selection.  Spans four decades so the
# CV can pick strong regularisation for small libraries and lighter touch for
# large ones.  Override by passing alphas= to CompletionPredictor().
RIDGE_ALPHAS: tuple[float, ...] = (0.01, 0.1, 1.0, 10.0, 100.0, 1_000.0)
PRED_KEY: str = "predicted_completion"

_DEFAULT_CKPT = Path.home() / ".phi" / "completion_predictor.npz"
_LOCK = threading.Lock()


def _ckpt_path() -> Path:
    override = os.environ.get("PHI_CP_CKPT")
    return Path(override) if override else _DEFAULT_CKPT


# ── feature helpers ────────────────────────────────────────────────────────────

def _dot_or_half(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine in [−1, 1] mapped to [0, 1], or 0.5 when either vec is empty/zero."""
    if a.size == 0 or b.size == 0 or a.size != b.size:
        return 0.5
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.5
    raw = float(np.dot(a, b) / (na * nb))
    return max(0.0, min(1.0, (raw + 1.0) / 2.0))   # shift [-1,1] → [0,1]


def _novelty(last_played_iso: str | None) -> float:
    if not last_played_iso:
        return NOVELTY_NEVER_HEARD
    try:
        days = (datetime.now() - datetime.fromisoformat(last_played_iso)).total_seconds() / 86400.0
        return min(1.0, 1.0 - math.exp(-days * math.log(2) / NOVELTY_HALF_LIFE))
    except (ValueError, TypeError):
        return NOVELTY_NEVER_HEARD


def _elo_norm(elo_raw: float) -> float:
    return max(0.0, min(1.0, (elo_raw - ELO_NORM_LO) / (ELO_NORM_HI - ELO_NORM_LO)))


def _skip_p(stats: dict) -> float:
    try:
        plays = int(stats.get("plays") or 0)
        skips = int(stats.get("skip_count") or 0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, skips / plays)) if plays > 0 else 0.0


def _mean_vec(paths: list[str], annotations: dict, key: str) -> np.ndarray:
    """Mean of annotation vecs for *paths*, or empty array if none exist."""
    vecs = []
    for p in paths:
        v = (annotations.get(p) or {}).get(key)
        if v and len(v) > 0:
            vecs.append(np.asarray(v, dtype=np.float32))
    if not vecs:
        return np.array([], dtype=np.float32)
    mean = np.mean(vecs, axis=0)
    norm = float(np.linalg.norm(mean))
    return (mean / norm) if norm > 0 else mean


def build_feature_row(
    ann: dict,
    stats: dict,
    session_gv: np.ndarray,
    session_mv: np.ndarray,
    hour: int,
) -> np.ndarray:
    """Build one N_FEATURES-d feature row for a (track, session_context) pair.

    Parameters
    ----------
    ann          Library.annotations[path]
    stats        Library.play_stats[path]
    session_gv   Session genre centroid (from TagEmbedder.session_genre_vec)
    session_mv   Session mood centroid  (from TagEmbedder.session_mood_vec)
    hour         Hour of day (0–23) for time encoding
    """
    track_gv = np.asarray(ann.get("genre_vec") or [], dtype=np.float32)
    track_mv = np.asarray(ann.get("mood_vec")  or [], dtype=np.float32)

    genre_dot   = _dot_or_half(track_gv, session_gv)
    mood_dot    = _dot_or_half(track_mv, session_mv)
    genre_norm  = float(np.linalg.norm(track_gv)) if track_gv.size > 0 else 0.0
    mood_norm   = float(np.linalg.norm(track_mv)) if track_mv.size > 0 else 0.0
    novelty     = _novelty(stats.get("last_played"))
    elo         = _elo_norm(float(stats.get("elo_score") or 1500.0))
    phi_rank    = float(ann.get("phi_rank") or 0.5)
    skip        = _skip_p(stats)
    plays_log   = math.log(max(1, int(stats.get("plays") or 1)))
    tod_sin     = math.sin(2 * math.pi * hour / 24)
    tod_cos     = math.cos(2 * math.pi * hour / 24)

    return np.array(
        [genre_dot, mood_dot, genre_norm, mood_norm, novelty, elo,
         phi_rank, skip, plays_log, tod_sin, tod_cos],
        dtype=np.float32,
    )


# ── CompletionPredictor ────────────────────────────────────────────────────────

class CompletionPredictor:
    """Ridge regression: (track_features, session_context) → predicted completion_rate.

    Trained on historical play data from Library.play_stats.  Predictions are
    written as "predicted_completion" annotations at session restore.
    """

    def __init__(self, alphas: tuple[float, ...] | list[float] = RIDGE_ALPHAS) -> None:
        self.alphas = tuple(alphas)
        self._coef: np.ndarray | None = None     # (N_FEATURES,)
        self._intercept: float = 0.5
        self._best_alpha: float | None = None    # set after CV fit
        self._fitted: bool = False

    # ── training ──────────────────────────────────────────────────────────────

    def fit(self, library: "Library") -> bool:
        """Fit on historical play data from *library*.

        Replays play history in chronological order; for each played track the
        session context is the mean embedding of the preceding SESSION_WINDOW
        tracks.  Requires at least MIN_SAMPLES rows.

        Returns True on success, False if insufficient data.
        """
        # Gather rows with both completion_rate and a timestamp
        played_raw: list[tuple[str, str, float]] = []
        for path, stats in library.play_stats.items():
            ts = stats.get("last_played")
            rate = stats.get("completion_rate")
            if ts and rate is not None and path in library.meta_cache:
                try:
                    played_raw.append((path, str(ts), float(rate)))
                except (TypeError, ValueError):
                    pass
        played_raw.sort(key=lambda t: t[1])   # chronological

        if len(played_raw) < MIN_SAMPLES:
            _log.info(
                "CompletionPredictor.fit: only %d labelled rows (need %d) — skipping",
                len(played_raw), MIN_SAMPLES,
            )
            return False

        rows: list[np.ndarray] = []
        targets: list[float] = []

        for i, (path, ts, rate) in enumerate(played_raw):
            window_paths = [played_raw[j][0] for j in range(max(0, i - SESSION_WINDOW), i)]
            session_gv = _mean_vec(window_paths, library.annotations, "genre_vec")
            session_mv = _mean_vec(window_paths, library.annotations, "mood_vec")
            ann   = library.annotations.get(path) or {}
            stats = library.play_stats.get(path) or {}
            try:
                hour = datetime.fromisoformat(ts).hour
            except (ValueError, TypeError):
                hour = 12
            row = build_feature_row(ann, stats, session_gv, session_mv, hour)
            rows.append(row)
            targets.append(rate)

        X = np.stack(rows, axis=0)         # (n, N_FEATURES)
        y = np.array(targets, dtype=np.float32)

        try:
            from sklearn.linear_model import RidgeCV
            # gcv_mode="auto" uses efficient generalised cross-validation (O(n²)
            # at worst), which avoids k-fold noise on small listening histories.
            model = RidgeCV(alphas=self.alphas, fit_intercept=True, gcv_mode="auto")
            model.fit(X, y)
            self._coef = model.coef_.astype(np.float32)
            self._intercept = float(model.intercept_)
            self._best_alpha = float(model.alpha_)
            self._fitted = True
            _log.info(
                "CompletionPredictor.fit: n=%d  best_alpha=%.4g  intercept=%.3f",
                len(rows), self._best_alpha, self._intercept,
            )
            return True
        except ImportError:
            _log.warning("CompletionPredictor.fit: sklearn not available")
            return False
        except Exception as exc:
            _log.warning("CompletionPredictor.fit failed: %s", exc)
            return False

    # ── inference ─────────────────────────────────────────────────────────────

    def predict_one(
        self,
        ann: dict,
        stats: dict,
        session_gv: np.ndarray,
        session_mv: np.ndarray,
        hour: int | None = None,
    ) -> float | None:
        """Predict completion_rate for one track. None when not fitted."""
        if not self._fitted or self._coef is None:
            return None
        if hour is None:
            hour = datetime.now().hour
        row = build_feature_row(ann, stats, session_gv, session_mv, hour)
        pred = float(np.dot(self._coef, row) + self._intercept)
        return max(0.0, min(1.0, pred))

    def predict_all(self, library: "Library") -> dict[str, float]:
        """Predict completion_rate for every track under the current session context.

        Uses the last SESSION_WINDOW played tracks as the session centroid.
        Returns {} when not fitted.
        """
        if not self._fitted or self._coef is None:
            return {}

        # Current session context
        recent = _recent_paths(library, SESSION_WINDOW)
        session_gv = _mean_vec(recent, library.annotations, "genre_vec")
        session_mv = _mean_vec(recent, library.annotations, "mood_vec")
        hour = datetime.now().hour

        scores: dict[str, float] = {}
        for path in library.playlist:
            ann   = library.annotations.get(path) or {}
            stats = library.play_stats.get(path) or {}
            pc = self.predict_one(ann, stats, session_gv, session_mv, hour)
            if pc is not None:
                scores[path] = pc
        _log.info(
            "CompletionPredictor.predict_all: predicted %d/%d tracks",
            len(scores), len(library.playlist),
        )
        return scores

    def annotate(
        self,
        library: "Library",
        scores: dict[str, float],
        *,
        key: str = PRED_KEY,
        overwrite: bool = True,
    ) -> int:
        """Write *scores* into library.annotations[path][key].

        Defaults overwrite=True — session-start predictions supersede stale values.
        Returns the number of annotations written.
        """
        n = 0
        for path, score in scores.items():
            ann = library.annotations.setdefault(path, {})
            if overwrite or not ann.get(key):
                ann[key] = round(score, 4)
                n += 1
        _log.info("CompletionPredictor.annotate: wrote %s for %d tracks", key, n)
        return n

    def fit_and_annotate(self, library: "Library") -> bool:
        """Fit, predict for all tracks, and write annotations.  Returns True on success."""
        if not self.fit(library):
            return False
        scores = self.predict_all(library)
        if scores:
            self.annotate(library, scores)
        return bool(scores)

    # ── persistence ───────────────────────────────────────────────────────────

    def save(self, path: str | Path | None = None) -> None:
        """Save Ridge coefficients to .npz."""
        if not self._fitted or self._coef is None:
            _log.warning("CompletionPredictor.save: nothing to save (not fitted)")
            return
        p = Path(path) if path else _ckpt_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            p,
            coef=self._coef,
            intercept=np.array([self._intercept], dtype=np.float32),
            best_alpha=np.array([self._best_alpha or 0.0], dtype=np.float32),
        )
        _log.info("CompletionPredictor.save → %s", p)

    @classmethod
    def load(cls, path: str | Path | None = None) -> "CompletionPredictor | None":
        """Load from .npz.  Returns None if absent or corrupt."""
        p = Path(path) if path else _ckpt_path()
        if not p.exists():
            return None
        try:
            data = np.load(p, allow_pickle=False)
            obj = cls()
            obj._coef = data["coef"].astype(np.float32)
            obj._intercept = float(data["intercept"][0])
            obj._best_alpha = float(data["best_alpha"][0]) if "best_alpha" in data else None
            obj._fitted = True
            _log.info("CompletionPredictor.load ← %s", p)
            return obj
        except Exception as exc:
            _log.warning("CompletionPredictor.load failed: %s", exc)
            return None


# ── session helpers ────────────────────────────────────────────────────────────

def _recent_paths(library: "Library", window: int) -> list[str]:
    """The last *window* played paths sorted by last_played, most recent first."""
    played = [
        (p, s.get("last_played", ""))
        for p, s in library.play_stats.items()
        if s.get("last_played") and p in library.meta_cache
    ]
    played.sort(key=lambda t: t[1], reverse=True)
    return [p for p, _ in played[:window]]


# ── module-level singleton (mirrors _embed.py / coplay_rank.py pattern) ────────

_predictor: CompletionPredictor | None = None
_fitted_flag: bool = False
_fit_lock = threading.Lock()


def maybe_predict_and_annotate(library: "Library") -> bool:
    """Fit CompletionPredictor on play history, then annotate all tracks.

    Called once at session restore after TagEmbedder and CoPlayRanker have run
    (annotations must already have genre_vec, mood_vec, phi_rank).

    Idempotent — returns True immediately on subsequent calls.
    Returns True on success, False if too few plays or sklearn missing.
    """
    global _predictor, _fitted_flag
    with _fit_lock:
        if _fitted_flag:
            return True

    try:
        predictor = CompletionPredictor()
        ok = predictor.fit_and_annotate(library)
        if ok:
            try:
                predictor.save()
            except Exception as exc:
                _log.warning("CompletionPredictor.save failed: %s", exc)
        with _fit_lock:
            _predictor = predictor
            _fitted_flag = True
        return ok
    except Exception as exc:
        _log.warning("maybe_predict_and_annotate failed: %s", exc)
        return False


def get_predictor() -> "CompletionPredictor | None":
    """Return the module-level predictor, or None if not yet fitted."""
    return _predictor


def refetch_predictor() -> None:
    """Reset the singleton (for tests / forced refit)."""
    global _predictor, _fitted_flag
    with _fit_lock:
        _predictor = None
        _fitted_flag = False
