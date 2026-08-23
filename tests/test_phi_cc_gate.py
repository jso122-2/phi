"""F_ADAPTIVE_CAPACITY + F_CC budget gate in the Phi ranker."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from phi.core.library import Library
from phi.core.ranker import (
    TrackRanker,
    RankContext,
    bind_floor,
    session_capacity_signals,
    adaptive_capacity,
    cc_budget_score,
)
from phi.core.ranker._constants import (
    AC_WEIGHT_N,
    AC_WEIGHT_S,
    AC_WEIGHT_T,
    CC_CEILING,
)


def test_adaptive_capacity_equal_weights():
    ac = adaptive_capacity(1.0, 0.0, 0.0)
    assert ac == pytest.approx(AC_WEIGHT_N)


def test_cc_rises_with_headroom_falls_with_pressure():
    tight = cc_budget_score(0.0, 1.0, 1.0)
    roomy = cc_budget_score(CC_CEILING, 1.0, 1.0)
    cheap = cc_budget_score(CC_CEILING, 0.25, 1.0)
    assert roomy > tight
    assert cheap > roomy
    assert tight == pytest.approx(0.0)


def test_cc_zero_pressure_does_not_divide_by_zero():
    val = cc_budget_score(0.5, 0.0, 1.0)
    assert val == val
    assert abs(val) < 1e12


def _lib_with_tracks() -> tuple[Library, list[str]]:
    lib = Library()
    paths = [f"/tmp/cc{i}.mp3" for i in range(4)]
    lib.playlist = list(paths)
    for p in paths:
        lib.meta_cache[p] = {"genre": "house"}
        lib.annotations[p] = {"phi_rank": 0.5, "key_confidence": 1.0}
        lib.play_stats[p] = {"plays": 1, "skip_count": 0, "completion_rate": 1.0}
    return lib, paths


def test_ranker_cc_budget_penalises_skips():
    lib, paths = _lib_with_tracks()
    clean, skipped = paths[0], paths[1]
    lib.play_stats[skipped] = {"plays": 4, "skip_count": 4, "completion_rate": 0.1}
    ranker = TrackRanker()
    ctx = RankContext()
    assert ranker.cc_budget(skipped, lib, ctx) < ranker.cc_budget(clean, lib, ctx)


def test_candidates_drops_below_average_cc():
    lib, paths = _lib_with_tracks()
    bad = paths[0]
    lib.play_stats[bad] = {
        "plays": 8,
        "skip_count": 8,
        "completion_rate": 0.0,
        "elo_score": 1500.0,
    }
    result = TrackRanker().candidates(lib, current_path=None, n=2)
    assert bad not in result
    assert len(result) == 2


def _fake_floor(code_coherence: float, commands_z: float = 0.0) -> SimpleNamespace:
    def hub(coh: float, z: float = 0.0) -> SimpleNamespace:
        return SimpleNamespace(coherence=coh, z_awareness=z, steps=0)

    hubs = {
        "CODE": hub(code_coherence),
        "HOME": hub(1.0),
        "MATH": hub(1.0),
        "COMMANDS": hub(1.0, commands_z),
        "agent-context": hub(1.0),
    }
    bridge = SimpleNamespace(
        _hubs=hubs,
        coherence_floor=0.50,
        z_spawn_threshold=2.5,
    )
    return SimpleNamespace(
        _bridge=bridge,
        when_floor_shifts=lambda shard, handler: None,
    )


def test_low_code_coherence_reduces_adaptive_capacity():
    import phi.core.ranker._context as rc

    ctx = RankContext()
    prev = rc._floor
    try:
        bind_floor(_fake_floor(1.0))
        ac_high, tcv_high = session_capacity_signals(ctx)
        bind_floor(_fake_floor(0.50))
        ac_low, tcv_low = session_capacity_signals(ctx)
        assert ac_high > ac_low
        assert tcv_high > tcv_low
        assert ac_high - ac_low == pytest.approx(AC_WEIGHT_S)
    finally:
        rc._floor = prev


def test_hot_commands_z_cuts_tracer_slack():
    import phi.core.ranker._context as rc

    ctx = RankContext()
    prev = rc._floor
    try:
        bind_floor(_fake_floor(1.0, commands_z=0.0))
        ac_cold, _ = session_capacity_signals(ctx)
        bind_floor(_fake_floor(1.0, commands_z=2.5))
        ac_hot, _ = session_capacity_signals(ctx)
        assert ac_cold > ac_hot
        assert ac_cold - ac_hot == pytest.approx(AC_WEIGHT_T)
    finally:
        rc._floor = prev


def test_package_exports_reach_cc_and_capacity():
    from workers.cairrn import f_adaptive_capacity, f_cc_energy_budget
    from phi.core.ranker import TrackRanker, adaptive_capacity, cc_budget_score

    assert callable(f_adaptive_capacity)
    assert callable(f_cc_energy_budget)
    assert callable(adaptive_capacity)
    assert callable(cc_budget_score)
    assert callable(TrackRanker().cc_budget)
    assert callable(TrackRanker().adaptive_capacity)
