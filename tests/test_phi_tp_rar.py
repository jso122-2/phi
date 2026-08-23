"""F_TP_RAR — Time-Penalised Risk Adjusted Return in the Phi ranker."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from phi.core.library import Library
from phi.core.ranker import RankContext, TrackRanker, tp_rar_score, TP_RAR_LAMBDA
from phi.core.ranker._tp_rar import _confidence_level, _skip_pressure, _time_delta


def test_high_confidence_beats_low_confidence():
    high = tp_rar_score(c_e=0.8, cl_e=1.0, dt=0.0, p=0.0)
    low  = tp_rar_score(c_e=0.8, cl_e=0.0, dt=0.0, p=0.0)
    assert high > low
    assert high - low == pytest.approx(TP_RAR_LAMBDA)


def test_time_and_skip_pressure_penalise():
    clean = tp_rar_score(c_e=0.8, cl_e=1.0, dt=0.0, p=0.0)
    stale = tp_rar_score(c_e=0.8, cl_e=1.0, dt=2.0, p=0.5)
    assert stale < clean
    assert clean - stale == pytest.approx(1.0)


def test_moving_average_scales():
    raw = tp_rar_score(c_e=0.6, cl_e=1.0, dt=0.0, p=0.0, conf_ma=1.0)
    half = tp_rar_score(c_e=0.6, cl_e=1.0, dt=0.0, p=0.0, conf_ma=0.5)
    assert half == pytest.approx(raw / 0.5)


def test_zero_ma_does_not_divide_by_zero():
    val = tp_rar_score(c_e=0.5, cl_e=1.0, dt=0.0, p=0.0, conf_ma=0.0)
    assert val == val  # not NaN
    assert abs(val) < 1e12


def test_confidence_level_averages_available_signals():
    cl = _confidence_level(
        {"key_confidence": 0.8, "bpm_confidence": 0.4},
        {"completion_rate": 1.0},
    )
    assert cl == pytest.approx((0.8 + 0.4 + 1.0) / 3.0)


def test_confidence_level_neutral_when_empty():
    assert _confidence_level({}, {}) == 0.5


def test_skip_pressure_is_skip_ratio():
    assert _skip_pressure({"plays": 4, "skip_count": 2}) == pytest.approx(0.5)
    assert _skip_pressure({}) == 0.0


def test_time_delta_zero_if_never_played():
    assert _time_delta({}) == 0.0


def test_time_delta_abandon_from_skip():
    assert _time_delta({"completion_rate": 0.0}) == pytest.approx(1.0)
    assert _time_delta({"completion_rate": 1.0}) == pytest.approx(0.0)


def test_time_delta_in_half_lives():
    last = (datetime.now() - timedelta(days=14)).isoformat()
    dt = _time_delta({"last_played": last})
    assert dt == pytest.approx(1.0, abs=0.05)


def _lib_with_tracks() -> Library:
    lib = Library()
    paths = [f"/tmp/t{i}.mp3" for i in range(4)]
    lib.playlist = list(paths)
    for p in paths:
        lib.meta_cache[p] = {"genre": "house"}
        lib.annotations[p] = {"phi_rank": 0.5, "key_confidence": 1.0}
        lib.play_stats[p] = {"plays": 1, "skip_count": 0, "completion_rate": 1.0}
    return lib, paths


def test_ranker_tp_rar_penalises_skips():
    lib, paths = _lib_with_tracks()
    clean, skipped = paths[0], paths[1]
    lib.play_stats[skipped] = {
        "plays": 4,
        "skip_count": 4,
        "completion_rate": 0.1,
        "last_played": (datetime.now() - timedelta(days=28)).isoformat(),
    }
    ranker = TrackRanker()
    ctx = RankContext()
    assert ranker.tp_rar(skipped, lib, ctx) < ranker.tp_rar(clean, lib, ctx)


def test_compute_scup_uses_real_tp_rar():
    lib, paths = _lib_with_tracks()
    skipped = paths[1]
    lib.play_stats[skipped] = {
        "plays": 4,
        "skip_count": 4,
        "completion_rate": 0.1,
        "last_played": (datetime.now() - timedelta(days=28)).isoformat(),
    }
    ranker = TrackRanker()
    ctx = RankContext()
    assert ranker.compute_scup(skipped, lib, ctx) < ranker.compute_scup(paths[0], lib, ctx)


def test_candidates_drops_below_average_tp_rar():
    lib, paths = _lib_with_tracks()
    bad = paths[0]
    # No last_played — must not land in RankContext.recent_paths (blocked).
    lib.play_stats[bad] = {
        "plays": 8,
        "skip_count": 8,
        "completion_rate": 0.0,
        "elo_score": 1500.0,
    }
    ranker = TrackRanker()
    result = ranker.candidates(lib, current_path=None, n=2)
    assert bad not in result
    assert len(result) == 2


def test_rank_by_scup_overrides_phi_rank_when_skipped():
    """A high phi_rank skip-magnet must sort below a lower-rank clean track."""
    lib, paths = _lib_with_tracks()
    hot, clean = paths[0], paths[1]
    lib.annotations[hot]["phi_rank"] = 0.99
    lib.annotations[clean]["phi_rank"] = 0.20
    lib.play_stats[hot] = {
        "plays": 8,
        "skip_count": 8,
        "completion_rate": 0.0,
        "last_played": (datetime.now() - timedelta(days=28)).isoformat(),
    }
    ranked = TrackRanker().rank_by_scup(paths, lib)
    assert ranked.index(clean) < ranked.index(hot)


def test_nudge_follows_scup_not_phi_rank():
    """Pending queue slots follow SCUP order, not raw RankArm phi_rank."""
    from phi.core.queue import QueueEngine

    lib, paths = _lib_with_tracks()
    skipped, clean = paths[2], paths[3]
    lib.annotations[skipped]["phi_rank"] = 0.95
    lib.annotations[clean]["phi_rank"] = 0.40
    lib.play_stats[skipped] = {
        "plays": 8,
        "skip_count": 8,
        "completion_rate": 0.0,
        "last_played": (datetime.now() - timedelta(days=28)).isoformat(),
    }

    q = QueueEngine()
    q.queue = [0, 1, 2, 3]
    q.pos = 0
    ranked = TrackRanker().rank_by_scup(paths, lib)
    moved = q.nudge(ranked, lib)
    assert moved == 2
    assert q.queue[:2] == [0, 1]
    assert q.queue[2] == 3
    assert q.queue[3] == 2


def test_bridge_on_write_emits_scup_order():
    """PhiTracerBridge.on_write must pass SCUP order, not phi_rank order."""
    from types import SimpleNamespace

    import numpy as np

    from phi.graph.phi_tracer_bridge import PhiTracerBridge

    lib, paths = _lib_with_tracks()
    skipped, clean = paths[0], paths[1]
    # RankArm would put skipped first; skip pressure must reverse that.
    ranks = [0.95, 0.40, 0.50, 0.50]
    lib.play_stats[skipped] = {
        "plays": 8,
        "skip_count": 8,
        "completion_rate": 0.0,
        "last_played": (datetime.now() - timedelta(days=28)).isoformat(),
    }

    received: list[list[str]] = []
    n = len(paths)
    out = SimpleNamespace(
        prune=np.zeros(n),
        rank=np.array(ranks, dtype=float),
        resurface=np.zeros(n),
        sprout=np.zeros(n),
        cluster=np.ones((n, 2)) * 0.5,
        tag=np.zeros((n, 4)),
        graft=np.zeros((n, n)),
        merge=np.zeros((n, n)),
        coherence_score=1.0,
        write_gated=True,
    )
    snap = SimpleNamespace(paths=paths)
    PhiTracerBridge(lib, on_write=received.append).write(out, snap)

    assert received, "on_write should fire after a successful write"
    order = received[0]
    assert order.index(clean) < order.index(skipped)
