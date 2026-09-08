"""Runtime stack: helm+prior C_E, song D4 on helm, dragon S_arc on spend."""
from __future__ import annotations

import pytest

from phi.core.library import Library
from phi.core.ranker import TrackRanker, blend_c_e, helm_score, spend_score
from phi.core.ranker._constants import PRED_PRIOR_HI, PRED_PRIOR_LO, SONG_D4_BLEND, WEIGHTS
from phi.core.ranker._scoring import _phi_rank
from phi.core.ranker._session import RankContext
from phi.core.ranker._track import _session_arc
from phi.engine.arc_scorer import ArcScorer


def test_blend_c_e_is_identity_without_predictor():
    assert blend_c_e(0.4, None, 1.0) == 0.4


def test_blend_c_e_gives_helm_more_weight_when_buoyant():
    rich = blend_c_e(0.2, 0.8, buoyancy=1.0)
    poor = blend_c_e(0.2, 0.8, buoyancy=0.0)
    assert rich == pytest.approx(PRED_PRIOR_LO * 0.8 + (1 - PRED_PRIOR_LO) * 0.2)
    assert poor == pytest.approx(PRED_PRIOR_HI * 0.8 + (1 - PRED_PRIOR_HI) * 0.2)
    assert abs(rich - 0.2) < abs(poor - 0.2)


def test_song_d4_rides_phi_rank_slot():
    assert _phi_rank({"phi_rank": 0.0}) == 0.0
    mixed = _phi_rank({"phi_rank": 0.0, "d4": 1.0})
    assert mixed == pytest.approx(SONG_D4_BLEND)


def test_score_blends_predictor_with_helm():
    lib = Library()
    lib.playlist = ["/a.mp3"]
    lib.meta_cache["/a.mp3"] = {"genre": "house"}
    lib.annotations["/a.mp3"] = {"predicted_completion": 0.9, "phi_rank": 0.5}
    lib.play_stats["/a.mp3"] = {"plays": 1, "skip_count": 0}
    ctx = RankContext()
    helm = helm_score("/a.mp3", lib, ctx, dict(WEIGHTS))
    score = TrackRanker().score("/a.mp3", lib, ctx)
    assert score == pytest.approx(blend_c_e(helm, 0.9, 0.5))
    assert score != pytest.approx(0.9)


def test_spend_penalises_skip_via_cognitive_pressure():
    lib = Library()
    clean, skipped = "/c.mp3", "/s.mp3"
    for p in (clean, skipped):
        lib.meta_cache[p] = {}
        lib.annotations[p] = {"buoyancy": 1.0, "d4_a": 10.0}
        lib.play_stats[p] = {"plays": 4, "skip_count": 0}
    lib.play_stats[skipped] = {"plays": 4, "skip_count": 4}
    ctx = RankContext()
    ac, tcv = 1.0, 1.0
    assert spend_score(skipped, lib, ctx, ac, tcv) < spend_score(clean, lib, ctx, ac, tcv)


def test_session_arc_prefers_continuation():
    lib = Library()
    lib.playlist = [f"/{i}.mp3" for i in range(6)]
    for i, p in enumerate(lib.playlist):
        lib.meta_cache[p] = {}
        lib.annotations[p] = {"d4_a": 10.0}
        lib.play_stats[p] = {"plays": 1, "skip_count": 0, "last_played": f"2026-01-0{i+1}T00:00:00"}
    jump = "/jump.mp3"
    lib.playlist.append(jump)
    lib.meta_cache[jump] = {}
    lib.annotations[jump] = {"d4_a": 20.0}
    lib.play_stats[jump] = {"plays": 1, "skip_count": 0}
    ctx = RankContext.from_library(lib, current_path=None)
    arc = _session_arc(lib, ctx)
    stay = arc.score_candidate(10.0)
    jolt = arc.score_candidate(20.0)
    assert stay > jolt
    assert jolt == pytest.approx(0.5) or jolt < stay
