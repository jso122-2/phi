"""D4 + GenrePredictor numpy path (sklearn / xgboost, no torch)."""
from __future__ import annotations

import pytest

from models.genre_predictor import GenrePredictor
from phi.models.d4_model import D4XGBoostModel, _build_feature_row
from phi.models.meta_clipper import MetaClipper, MetaClipperModel


def test_genre_predictor_artifacts_gate():
    ready = GenrePredictor.artifacts_ready()
    assert isinstance(ready, bool)


def test_meta_clipper_feeds_d4_features():
    sklearn = pytest.importorskip("sklearn")  # noqa: F841
    items = [
        (f"/tmp/c{i}.mp3", {
            "title": f"track {i} pulse",
            "artist": "tester",
            "album": "lab",
            "genre": "house" if i % 2 == 0 else "techno",
        })
        for i in range(8)
    ]
    clipper = MetaClipper()
    clipper.fit(items)
    model = MetaClipperModel(clipper)
    assert model.can_process(items[0][0], {})
    out = model.run(items[0][0], items[0][1])
    assert len(out["clipper_emb"]) == 36
    assert len(out["fold_bits"]) == 8
    assert "d4_b" in out
    row = _build_feature_row(out)
    assert row is not None
    assert row.shape == (45,)
    assert not model.can_process(items[0][0], out)


def test_d4_xgboost_fit_predict():
    pytest.importorskip("xgboost")
    pytest.importorskip("sklearn")
    items = [
        (f"/tmp/d{i}.mp3", {
            "title": f"song {i} wave",
            "artist": "lab",
            "album": "set",
            "genre": "ambient",
        })
        for i in range(10)
    ]
    clipper = MetaClipper()
    anns, rolling = clipper.run_batch(items)
    d4 = D4XGBoostModel(xgb_params={"n_estimators": 8, "max_depth": 2, "n_jobs": 1})
    info = d4.fit(anns, rolling)
    assert info["n_train"] >= 4
    pred = d4.run(items[0][0], anns[0])
    assert "d4_pred" in pred
    assert isinstance(pred["d4_pred"], float)
