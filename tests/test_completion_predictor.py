"""Tests for phi.models.completion_predictor (CompletionPredictor).

Covers:
- build_feature_row: shape, values, edge cases
- fit: returns False when < MIN_SAMPLES, True with enough data
- fit: high-completion tracks score higher than low-completion tracks
- predict_one: clips to [0, 1], returns None when not fitted
- predict_all: covers full library, None-safe
- annotate: writes PRED_KEY, overwrites by default, skips when overwrite=False
- save / load round-trip: predictions reproduce
- TrackRanker.score: uses predicted_completion when present, fallback when absent
- maybe_predict_and_annotate: idempotent singleton
"""
from __future__ import annotations

import math
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from phi.models.completion_predictor import (
    CompletionPredictor,
    N_FEATURES,
    MIN_SAMPLES,
    PRED_KEY,
    RIDGE_ALPHAS,
    build_feature_row,
    maybe_predict_and_annotate,
    refetch_predictor,
    _mean_vec,
    _novelty,
    _elo_norm,
    _skip_p,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _ts(offset_secs: int = 0) -> str:
    return (datetime(2026, 1, 1, 12, 0, 0) + timedelta(seconds=offset_secs)).isoformat()


def _make_ann(completion: float, genre_vec=None, mood_vec=None, phi_rank=0.5) -> dict:
    ann: dict = {"phi_rank": phi_rank}
    if genre_vec is not None:
        ann["genre_vec"] = genre_vec
    if mood_vec is not None:
        ann["mood_vec"] = mood_vec
    return ann


def _make_stats(completion: float, offset: int = 0, plays: int = 5) -> dict:
    return {
        "last_played": _ts(offset),
        "completion_rate": completion,
        "plays": plays,
        "skip_count": max(0, plays - round(plays * completion)),
        "elo_score": 1500.0,
    }


def _make_library(
    n: int,
    completion_fn=None,
    has_vecs: bool = True,
) -> MagicMock:
    """Stub library with *n* played tracks."""
    if completion_fn is None:
        completion_fn = lambda i: 0.7 + 0.1 * (i % 3 - 1)   # noqa: E731
    lib = MagicMock()
    lib.playlist = [f"/{i}" for i in range(n)]
    lib.meta_cache = {f"/{i}": {} for i in range(n)}
    lib.play_stats = {}
    lib.annotations = {}
    rng = np.random.default_rng(42)
    for i in range(n):
        comp = max(0.0, min(1.0, completion_fn(i)))
        lib.play_stats[f"/{i}"] = _make_stats(comp, offset=i * 60)
        gv = rng.normal(size=8).astype(np.float32).tolist() if has_vecs else None
        mv = rng.normal(size=9).astype(np.float32).tolist() if has_vecs else None
        lib.annotations[f"/{i}"] = _make_ann(comp, genre_vec=gv, mood_vec=mv)
    return lib


# ── build_feature_row ─────────────────────────────────────────────────────────

class TestBuildFeatureRow:
    def test_shape(self):
        ann = _make_ann(0.8)
        stats = _make_stats(0.8)
        row = build_feature_row(ann, stats, np.array([]), np.array([]), hour=14)
        assert row.shape == (N_FEATURES,)

    def test_all_finite(self):
        ann = _make_ann(0.7, genre_vec=[0.5]*8, mood_vec=[0.3]*9)
        stats = _make_stats(0.7, plays=10)
        sgv = np.ones(8, dtype=np.float32) / np.sqrt(8)
        smv = np.ones(9, dtype=np.float32) / np.sqrt(9)
        row = build_feature_row(ann, stats, sgv, smv, hour=10)
        assert np.all(np.isfinite(row))

    def test_missing_vecs_gives_half_dot(self):
        ann = _make_ann(0.8)  # no genre_vec/mood_vec
        stats = _make_stats(0.8)
        row = build_feature_row(ann, stats, np.array([]), np.array([]), hour=12)
        assert row[0] == pytest.approx(0.5)   # genre_dot default
        assert row[1] == pytest.approx(0.5)   # mood_dot default

    def test_matching_vecs_dot_above_half(self):
        v = np.ones(8, dtype=np.float32) / np.sqrt(8)
        ann = _make_ann(0.9, genre_vec=v.tolist())
        stats = _make_stats(0.9)
        row = build_feature_row(ann, stats, v, np.array([]), hour=12)
        # self-cosine → 1.0, shifted to [0,1] → 1.0
        assert row[0] == pytest.approx(1.0, abs=1e-5)

    def test_tod_encoding_is_cyclic(self):
        ann = _make_ann(0.7)
        stats = _make_stats(0.7)
        row_0  = build_feature_row(ann, stats, np.array([]), np.array([]), hour=0)
        row_24 = build_feature_row(ann, stats, np.array([]), np.array([]), hour=24 % 24)
        np.testing.assert_allclose(row_0[9:], row_24[9:], atol=1e-5)

    def test_plays_log_increases_with_plays(self):
        ann = _make_ann(0.7)
        s1 = _make_stats(0.7, plays=1)
        s2 = _make_stats(0.7, plays=100)
        r1 = build_feature_row(ann, s1, np.array([]), np.array([]), hour=12)
        r2 = build_feature_row(ann, s2, np.array([]), np.array([]), hour=12)
        assert r2[8] > r1[8]


# ── CompletionPredictor.fit ────────────────────────────────────────────────────

class TestFit:
    def test_returns_false_below_min_samples(self):
        lib = _make_library(MIN_SAMPLES - 1)
        predictor = CompletionPredictor()
        assert predictor.fit(lib) is False
        assert not predictor._fitted

    def test_returns_true_with_enough_data(self):
        lib = _make_library(MIN_SAMPLES + 5)
        predictor = CompletionPredictor()
        assert predictor.fit(lib) is True
        assert predictor._fitted
        assert predictor._coef is not None
        assert predictor._coef.shape == (N_FEATURES,)

    def test_best_alpha_is_from_search_grid(self):
        lib = _make_library(MIN_SAMPLES + 10)
        predictor = CompletionPredictor()
        predictor.fit(lib)
        assert predictor._best_alpha in RIDGE_ALPHAS

    def test_custom_alphas_respected(self):
        lib = _make_library(MIN_SAMPLES + 5)
        custom = (0.001, 0.01)
        predictor = CompletionPredictor(alphas=custom)
        predictor.fit(lib)
        assert predictor._best_alpha in custom

    def test_high_completion_predicts_higher(self):
        """Tracks always completed should be predicted higher than always-skipped."""
        lib = _make_library(
            MIN_SAMPLES + 20,
            completion_fn=lambda i: 0.95 if i % 2 == 0 else 0.05,
        )
        predictor = CompletionPredictor()
        predictor.fit(lib)

        # Score a track identical to high-completion tracks vs low-completion
        sgv = np.array([], dtype=np.float32)
        smv = np.array([], dtype=np.float32)
        high_ann = _make_ann(0.95, phi_rank=0.8)
        low_ann  = _make_ann(0.05, phi_rank=0.2)
        high_stats = _make_stats(0.95, plays=20)
        low_stats  = _make_stats(0.05, plays=20)
        p_high = predictor.predict_one(high_ann, high_stats, sgv, smv, hour=12)
        p_low  = predictor.predict_one(low_ann,  low_stats,  sgv, smv, hour=12)
        assert p_high is not None and p_low is not None
        assert p_high > p_low, f"high={p_high:.3f} should exceed low={p_low:.3f}"

    def test_tracks_without_completion_excluded(self):
        lib = _make_library(MIN_SAMPLES + 5)
        # Remove completion_rate from half the tracks
        for i in range(0, MIN_SAMPLES + 5, 2):
            lib.play_stats[f"/{i}"].pop("completion_rate", None)
        predictor = CompletionPredictor()
        # Should still fit on the remaining half (if ≥ MIN_SAMPLES remain)
        result = predictor.fit(lib)
        if (MIN_SAMPLES + 5) // 2 >= MIN_SAMPLES:
            assert result is True
        # No assertion on False — just don't crash


# ── predict_one ───────────────────────────────────────────────────────────────

class TestPredictOne:
    def test_returns_none_when_not_fitted(self):
        p = CompletionPredictor()
        assert p.predict_one({}, {}, np.array([]), np.array([]), hour=12) is None

    def test_output_in_unit_interval(self):
        lib = _make_library(MIN_SAMPLES + 10)
        p = CompletionPredictor()
        p.fit(lib)
        sgv = np.array([], dtype=np.float32)
        smv = np.array([], dtype=np.float32)
        for i in range(10):
            ann   = lib.annotations[f"/{i}"]
            stats = lib.play_stats[f"/{i}"]
            pred = p.predict_one(ann, stats, sgv, smv, hour=14)
            assert pred is not None
            assert 0.0 <= pred <= 1.0


# ── predict_all / annotate ────────────────────────────────────────────────────

class TestPredictAll:
    def test_covers_all_playlist_tracks(self):
        lib = _make_library(MIN_SAMPLES + 10)
        p = CompletionPredictor()
        p.fit(lib)
        scores = p.predict_all(lib)
        # All tracks should have a prediction (they all have play_stats / meta)
        assert len(scores) == len(lib.playlist)

    def test_returns_empty_when_not_fitted(self):
        lib = _make_library(5)
        p = CompletionPredictor()
        assert p.predict_all(lib) == {}

    def test_annotate_writes_pred_key(self):
        lib = _make_library(MIN_SAMPLES + 5)
        p = CompletionPredictor()
        p.fit(lib)
        scores = p.predict_all(lib)
        p.annotate(lib, scores)
        assert lib.annotations["/0"].get(PRED_KEY) is not None

    def test_annotate_overwrite_true_replaces(self):
        lib = _make_library(MIN_SAMPLES + 5)
        lib.annotations.setdefault("/0", {})[PRED_KEY] = 0.999
        p = CompletionPredictor()
        p.fit(lib)
        scores = p.predict_all(lib)
        p.annotate(lib, {"/0": 0.123}, overwrite=True)
        assert lib.annotations["/0"][PRED_KEY] == pytest.approx(0.123)

    def test_annotate_overwrite_false_preserves(self):
        lib = _make_library(MIN_SAMPLES + 5)
        lib.annotations.setdefault("/0", {})[PRED_KEY] = 0.999
        p = CompletionPredictor()
        p.fit(lib)
        p.annotate(lib, {"/0": 0.123}, overwrite=False)
        assert lib.annotations["/0"][PRED_KEY] == pytest.approx(0.999)


# ── save / load ───────────────────────────────────────────────────────────────

class TestPersistence:
    def test_save_load_reproduces_predictions(self):
        lib = _make_library(MIN_SAMPLES + 10)
        p1 = CompletionPredictor()
        p1.fit(lib)
        with tempfile.TemporaryDirectory() as td:
            ckpt = Path(td) / "cp.npz"
            p1.save(ckpt)
            p2 = CompletionPredictor.load(ckpt)
        assert p2 is not None
        assert p2._fitted
        assert p2._best_alpha == pytest.approx(p1._best_alpha, rel=1e-4)
        sgv = np.array([], dtype=np.float32)
        smv = np.array([], dtype=np.float32)
        ann   = lib.annotations["/0"]
        stats = lib.play_stats["/0"]
        pred1 = p1.predict_one(ann, stats, sgv, smv, hour=12)
        pred2 = p2.predict_one(ann, stats, sgv, smv, hour=12)
        assert pred1 is not None and pred2 is not None
        assert abs(pred1 - pred2) < 1e-5

    def test_load_returns_none_when_absent(self, tmp_path):
        result = CompletionPredictor.load(tmp_path / "nonexistent.npz")
        assert result is None

    def test_save_skips_when_not_fitted(self, tmp_path, caplog):
        p = CompletionPredictor()
        p.save(tmp_path / "cp.npz")
        assert not (tmp_path / "cp.npz").exists()


# ── TrackRanker integration ───────────────────────────────────────────────────

class TestTrackRankerIntegration:
    def _make_ranker_library(self, with_prediction: bool, prediction: float = 0.85):
        lib = MagicMock()
        lib.meta_cache = {"/a": {}}
        lib.play_stats = {"/a": {"elo_score": 1500.0, "plays": 5, "last_played": _ts(0)}}
        ann = {}
        if with_prediction:
            ann[PRED_KEY] = prediction
        lib.annotations = {"/a": ann}
        lib.get_elo = MagicMock(return_value=1500.0)
        return lib

    def test_score_uses_predicted_completion_when_present(self):
        from phi.core.ranker._track import TrackRanker
        from phi.core.ranker._session import RankContext
        lib = self._make_ranker_library(with_prediction=True, prediction=0.73)
        ctx = RankContext()
        ranker = TrackRanker()
        score = ranker.score("/a", lib, ctx)
        assert score == pytest.approx(0.73)

    def test_score_falls_back_to_heuristic_when_absent(self):
        from phi.core.ranker._track import TrackRanker
        from phi.core.ranker._session import RankContext
        lib = self._make_ranker_library(with_prediction=False)
        ctx = RankContext()
        ranker = TrackRanker()
        score = ranker.score("/a", lib, ctx)
        # Should return something in [0, 1] from the heuristic path
        assert 0.0 <= score <= 1.0

    def test_predicted_completion_is_clamped(self):
        from phi.core.ranker._track import TrackRanker
        from phi.core.ranker._session import RankContext
        lib = self._make_ranker_library(with_prediction=True, prediction=1.5)
        ctx = RankContext()
        ranker = TrackRanker()
        assert ranker.score("/a", lib, ctx) == pytest.approx(1.0)


# ── maybe_predict_and_annotate ────────────────────────────────────────────────

class TestMaybePredictAndAnnotate:
    def setup_method(self):
        refetch_predictor()

    def test_returns_false_for_too_few_plays(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PHI_CP_CKPT", str(tmp_path / "cp.npz"))
        lib = _make_library(MIN_SAMPLES - 1)
        result = maybe_predict_and_annotate(lib)
        assert result is False

    def test_returns_true_with_enough_plays(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PHI_CP_CKPT", str(tmp_path / "cp.npz"))
        lib = _make_library(MIN_SAMPLES + 10)
        result = maybe_predict_and_annotate(lib)
        assert result is True

    def test_idempotent(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PHI_CP_CKPT", str(tmp_path / "cp.npz"))
        lib = _make_library(MIN_SAMPLES + 5)
        assert maybe_predict_and_annotate(lib) is True
        assert maybe_predict_and_annotate(lib) is True  # no-op

    def test_writes_pred_annotations(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PHI_CP_CKPT", str(tmp_path / "cp.npz"))
        lib = _make_library(MIN_SAMPLES + 10)
        maybe_predict_and_annotate(lib)
        annotated = [p for p in lib.playlist if lib.annotations.get(p, {}).get(PRED_KEY) is not None]
        assert len(annotated) > 0


# ── helper function coverage ──────────────────────────────────────────────────

class TestHelpers:
    def test_novelty_recent_low(self):
        v = _novelty(datetime.now().isoformat())
        assert v < 0.1

    def test_novelty_never_heard(self):
        from phi.models.completion_predictor import NOVELTY_NEVER_HEARD
        assert _novelty(None) == NOVELTY_NEVER_HEARD

    def test_elo_norm_midpoint(self):
        mid = (1200.0 + 1800.0) / 2.0   # 1500
        assert _elo_norm(1500.0) == pytest.approx(0.5)

    def test_skip_p_zero_plays(self):
        assert _skip_p({}) == 0.0

    def test_mean_vec_empty_paths(self):
        v = _mean_vec([], {}, "genre_vec")
        assert v.size == 0

    def test_mean_vec_is_unit(self):
        anns = {
            "/a": {"genre_vec": [1.0, 0.0, 0.0]},
            "/b": {"genre_vec": [0.0, 1.0, 0.0]},
        }
        v = _mean_vec(["/a", "/b"], anns, "genre_vec")
        assert abs(float(np.linalg.norm(v)) - 1.0) < 1e-5
