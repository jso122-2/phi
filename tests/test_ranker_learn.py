"""Learned ranker WEIGHTS from skip / complete feedback."""
from __future__ import annotations

from datetime import datetime

import pytest

from phi.core.library import Library
from phi.core.ranker import (
    WEIGHTS,
    WEIGHT_KEYS,
    TrackRanker,
    active_weights,
    reset_learned,
)
from phi.core.ranker._learn import (
    dimension_scores,
    fit_from_play_stats,
    update_from_feedback,
)
from phi.core.ranker._session import RankContext


@pytest.fixture(autouse=True)
def _isolated_weights(tmp_path, monkeypatch):
    monkeypatch.setenv("PHI_RANKER_WEIGHTS", str(tmp_path / "ranker_weights.json"))
    reset_learned()
    yield
    reset_learned()


def _lib() -> Library:
    lib = Library()
    paths = [f"/tmp/learn-{i}.mp3" for i in range(4)]
    lib.playlist = list(paths)
    now = datetime.now().isoformat()
    for i, p in enumerate(paths):
        lib.meta_cache[p] = {"genre": "house" if i < 2 else "techno", "duration": 180}
        lib.annotations[p] = {"mood": "energetic", "phi_rank": 0.2 + 0.2 * i}
        lib.play_stats[p] = {
            "plays": 3,
            "skip_count": 0,
            "completion_rate": 1.0 if i < 2 else 0.1,
            "last_played": now,
        }
    return lib


def test_active_weights_default_to_prior():
    w = active_weights()
    assert set(w) == set(WEIGHT_KEYS)
    assert pytest.approx(sum(w.values()), abs=1e-9) == 1.0
    for k in WEIGHT_KEYS:
        assert w[k] == pytest.approx(WEIGHTS[k])


def test_complete_boosts_high_dimension():
    feats = {k: 0.1 for k in WEIGHT_KEYS}
    feats["genre"] = 1.0
    before = active_weights()["genre"]
    after = update_from_feedback(feats, y=1.0)
    assert after["genre"] > before
    assert pytest.approx(sum(after.values()), abs=1e-9) == 1.0
    for v in after.values():
        assert v >= 0.05 - 1e-9


def test_skip_shrinks_high_dimension():
    feats = {k: 0.1 for k in WEIGHT_KEYS}
    feats["mood"] = 1.0
    before = active_weights()["mood"]
    after = update_from_feedback(feats, y=-1.0)
    assert after["mood"] < before


def test_implicit_elo_learns_on_skip():
    lib = _lib()
    skipped = lib.playlist[-1]
    lib.play_stats[skipped]["completion_rate"] = 0.1
    before = dict(active_weights())
    TrackRanker().implicit_elo_update(skipped, lib)
    after = active_weights()
    assert after != before
    assert pytest.approx(sum(after.values()), abs=1e-9) == 1.0


def test_implicit_elo_ignores_ambiguous_completion():
    lib = _lib()
    path = lib.playlist[0]
    lib.play_stats[path]["completion_rate"] = 0.5
    before = dict(active_weights())
    TrackRanker().implicit_elo_update(path, lib)
    assert active_weights() == before


def test_fit_from_play_stats_steps():
    lib = _lib()
    n = fit_from_play_stats(lib)
    assert n == 4
    w = active_weights()
    assert pytest.approx(sum(w.values()), abs=1e-9) == 1.0


def test_exclude_keeps_departed_track_out_of_session():
    lib = _lib()
    gone = lib.playlist[0]
    ctx = RankContext.from_library(lib, None, exclude=gone)
    assert gone not in ctx.recent_paths
    feats = dimension_scores(gone, lib, ctx)
    assert set(feats) == set(WEIGHT_KEYS)
    for v in feats.values():
        assert 0.0 <= v <= 1.0
