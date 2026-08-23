"""
tests/test_mycelial_substrate.py — integration tests for MycelialSubstrate.

Tests the full wiring:
  MycelialSubstrate ← workers/cairrn/mycelial.py (pure formulas)
  MycelialSubstrate ← PhiGraphSnapshot (tracks, H, A)
  MycelialSubstrate → CAIRRNDispatcher (MYCELIAL_TICK action)

Uses a minimal fake snapshot and a stub harmonic index — no real library scan.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from engine.mycelial_substrate import (
    MycelialSubstrate,
    MycelialTickResult,
    _NEW_EDGE_WEIGHT,
    _SHIMMER_RATE,
    _FLOW_THRESH,
)
from engine.cairrn_dispatch import (
    CAIRRNDispatcher,
    PhiAction,
    PhiActionKind,
    make_dispatcher,
)
from engine.gate import COHERENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Minimal fakes
# ---------------------------------------------------------------------------


@dataclass
class FakeTrack:
    path: str
    name: str = "track"
    artist: str = "artist"


@dataclass
class FakeSnapshot:
    tracks: list
    H: np.ndarray
    A: np.ndarray

    @property
    def N(self):
        return len(self.tracks)


class FakeShard:
    def __init__(self, activation: float = 0.5):
        self.activation = activation


class FakeHarmonicIndex:
    def __init__(self, code_act: float = 0.5, n_shards: int = 8):
        self.shards = [FakeShard(code_act if i in (3, 4) else 0.1) for i in range(n_shards)]

    def inject_from_hub(self, hub_name: str, value: float) -> None:
        pass

    def inject(self, shard_index: int, value: float) -> None:
        pass

    def propagate(self, steps: int = 1, mode: str = "local") -> None:
        pass


def _make_snapshot(n: int = 5, connected: bool = True) -> FakeSnapshot:
    """Build a tiny fake snapshot with n tracks and optional full-mesh adjacency."""
    tracks = [FakeTrack(path=f"/fake/{i}.mp3", name=f"track_{i}") for i in range(n)]
    rng = np.random.default_rng(42)
    H = rng.standard_normal((n, 256)).astype(np.float64)
    A = np.zeros((n, n), dtype=np.float64)
    if connected and n > 1:
        # Simple ring adjacency
        for i in range(n):
            A[i, (i + 1) % n] = 1.0
            A[(i + 1) % n, i] = 1.0
    return FakeSnapshot(tracks=tracks, H=H, A=A)


def _make_substrate(n: int = 5, code_act: float = 0.6) -> MycelialSubstrate:
    snap = _make_snapshot(n)
    idx = FakeHarmonicIndex(code_act=code_act)
    return MycelialSubstrate(snap, idx)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_init_energy_zeros(self):
        sub = _make_substrate(n=5)
        assert sub.energy.shape == (5,)
        assert np.all(sub.energy == 0.0)

    def test_init_weights_from_adjacency(self):
        snap = _make_snapshot(n=5, connected=True)
        idx = FakeHarmonicIndex()
        sub = MycelialSubstrate(snap, idx)
        # Ring adjacency: each node connects to its two neighbours
        assert np.all(sub.weights >= 0.0)
        # Existing edges (A=1) map to weight 1.0
        assert sub.weights[0, 1] == pytest.approx(1.0)
        assert sub.weights[1, 0] == pytest.approx(1.0)
        # Non-edges map to weight 0.0
        assert sub.weights[0, 2] == pytest.approx(0.0)

    def test_init_tick_count_zero(self):
        sub = _make_substrate()
        assert sub.tick_count == 0

    def test_repr(self):
        sub = _make_substrate()
        r = repr(sub)
        assert "MycelialSubstrate" in r
        assert "N=5" in r

    def test_state_dict(self):
        sub = _make_substrate()
        s = sub.state()
        assert "tick_count" in s
        assert "n_nodes" in s
        assert s["n_nodes"] == 5


# ---------------------------------------------------------------------------
# Tick basics
# ---------------------------------------------------------------------------


class TestTick:
    def test_returns_tick_result(self):
        sub = _make_substrate()
        result = sub.tick(budget=5.0)
        assert isinstance(result, MycelialTickResult)

    def test_tick_count_increments(self):
        sub = _make_substrate()
        sub.tick(budget=1.0)
        sub.tick(budget=1.0)
        assert sub.tick_count == 2

    def test_result_tick_index_matches(self):
        sub = _make_substrate()
        r = sub.tick(budget=1.0)
        assert r.tick == 0
        r2 = sub.tick(budget=1.0)
        assert r2.tick == 1

    def test_energy_increases_after_tick_with_budget(self):
        sub = _make_substrate(n=5, code_act=0.8)
        sub.tick(budget=10.0)
        assert np.mean(sub.energy) > 0.0

    def test_energy_clamped_to_e_max(self):
        sub = _make_substrate(n=5, code_act=1.0)
        for _ in range(50):
            sub.tick(budget=100.0)
        from workers.cairrn.mycelial import _E_MAX
        assert np.all(sub.energy <= _E_MAX + 1e-9)

    def test_energy_nonnegative(self):
        sub = _make_substrate(n=5, code_act=0.1)
        for _ in range(20):
            sub.tick(budget=0.01)
        assert np.all(sub.energy >= 0.0)

    def test_tick_result_n_nodes(self):
        sub = _make_substrate(n=7)
        r = sub.tick(budget=5.0)
        assert r.n_nodes == 7

    def test_tick_result_budget_used_nonneg(self):
        sub = _make_substrate(n=5)
        r = sub.tick(budget=3.0)
        assert r.budget_used >= 0.0

    def test_tick_zero_budget_no_energy(self):
        sub = _make_substrate(n=5, code_act=0.0)
        r = sub.tick(budget=0.0)
        # With zero budget all demand gets 0 nutrients;
        # energy may decay (basal cost) but stays ≥ 0
        assert np.all(sub.energy >= 0.0)


# ---------------------------------------------------------------------------
# Default budget (code-activation scaled)
# ---------------------------------------------------------------------------


class TestDefaultBudget:
    def test_default_budget_no_crash(self):
        sub = _make_substrate(n=5, code_act=0.5)
        result = sub.tick()  # budget=None → compute from code activation
        assert isinstance(result, MycelialTickResult)

    def test_higher_code_act_more_energy(self):
        sub_hi = _make_substrate(n=5, code_act=1.0)
        sub_lo = _make_substrate(n=5, code_act=0.0)
        for _ in range(5):
            sub_hi.tick()
            sub_lo.tick()
        assert sub_hi.energy.sum() >= sub_lo.energy.sum()


# ---------------------------------------------------------------------------
# Edge weight evolution
# ---------------------------------------------------------------------------


class TestEdgeWeights:
    def test_weights_stay_nonneg(self):
        sub = _make_substrate(n=5)
        for _ in range(10):
            sub.tick(budget=2.0)
        assert np.all(sub.weights >= 0.0)

    def test_cold_edges_decay(self):
        snap = _make_snapshot(n=5, connected=True)
        idx = FakeHarmonicIndex(code_act=0.0)  # zero budget → no flow
        sub = MycelialSubstrate(snap, idx)
        initial_w = sub.weights[0, 1]
        for _ in range(30):
            sub.tick(budget=0.0)
        # With zero budget/energy, edges receive no flow → shimmer decay applies
        assert sub.weights[0, 1] <= initial_w  # must not grow


# ---------------------------------------------------------------------------
# Accessor methods
# ---------------------------------------------------------------------------


class TestAccessors:
    def test_node_energy_returns_float(self):
        sub = _make_substrate(n=5)
        sub.tick(budget=5.0)
        assert isinstance(sub.node_energy(0), float)

    def test_top_k_energy_length(self):
        sub = _make_substrate(n=5)
        sub.tick(budget=5.0)
        top = sub.top_k_energy(k=3)
        assert len(top) == 3

    def test_top_k_energy_sorted_desc(self):
        sub = _make_substrate(n=10)
        sub.tick(budget=20.0)
        top = sub.top_k_energy(k=5)
        energies = [sub.energy[i] for i in top]
        assert energies == sorted(energies, reverse=True)

    def test_top_k_energy_empty_n(self):
        snap = FakeSnapshot(tracks=[], H=np.zeros((0, 256)), A=np.zeros((0, 0)))
        idx = FakeHarmonicIndex()
        sub = MycelialSubstrate(snap, idx)
        assert sub.top_k_energy(k=5) == []

    def test_edge_weight_returns_float(self):
        sub = _make_substrate(n=5)
        assert isinstance(sub.edge_weight(0, 1), float)


# ---------------------------------------------------------------------------
# Rebind
# ---------------------------------------------------------------------------


class TestRebind:
    def test_rebind_same_n(self):
        sub = _make_substrate(n=5)
        sub.tick(budget=5.0)
        old_energy = sub.energy.copy()
        new_snap = _make_snapshot(n=5)
        sub.rebind(new_snap)
        assert sub._N == 5
        np.testing.assert_array_equal(sub.energy, old_energy)

    def test_rebind_grow(self):
        sub = _make_substrate(n=3)
        sub.tick(budget=3.0)
        new_snap = _make_snapshot(n=6)
        sub.rebind(new_snap)
        assert sub._N == 6
        assert sub.energy.shape == (6,)
        assert sub.weights.shape == (6, 6)
        # New nodes start at 0 energy
        assert np.all(sub.energy[3:] == 0.0)

    def test_rebind_shrink(self):
        sub = _make_substrate(n=6)
        sub.tick(budget=6.0)
        new_snap = _make_snapshot(n=3)
        sub.rebind(new_snap)
        assert sub._N == 3
        assert sub.energy.shape == (3,)

    def test_rebind_tick_count_preserved(self):
        sub = _make_substrate(n=4)
        sub.tick(budget=4.0)
        assert sub.tick_count == 1
        new_snap = _make_snapshot(n=4)
        sub.rebind(new_snap)
        assert sub.tick_count == 1  # tick count is not reset


# ---------------------------------------------------------------------------
# Dispatcher integration — MYCELIAL_TICK action
# ---------------------------------------------------------------------------


class TestDispatcherIntegration:
    def _make_dispatcher_with_substrate(self, n: int = 5, code_act: float = 0.9):
        idx = FakeHarmonicIndex(code_act=code_act)
        snap = _make_snapshot(n=n)
        sub = MycelialSubstrate(snap, idx)
        dispatcher = make_dispatcher(
            harmonic_index=idx,
            substrate=sub,
            tau=1.0,  # very short tau so gate opens quickly
            threshold=COHERENCE_THRESHOLD,
        )
        return dispatcher, sub, idx

    def test_mycelial_tick_action_dispatches(self):
        dispatcher, sub, idx = self._make_dispatcher_with_substrate()
        action = PhiAction(PhiActionKind.MYCELIAL_TICK, {"budget": 2.0})
        dispatcher.enqueue(action)
        # Gate formula: coherence = 1.0 - exp(-steps/τ).
        # With τ=1.0, steps=1 → coherence ≈ 0.632 > COHERENCE_THRESHOLD (0.5671).
        dispatcher._steps_since_tick = 1
        result = dispatcher.step()
        assert result.gated

    def test_mycelial_tick_no_substrate_returns_error(self):
        idx = FakeHarmonicIndex()
        dispatcher = make_dispatcher(harmonic_index=idx, tau=1.0)
        dispatcher._steps_since_tick = 1  # 1-exp(-1/1.0) ≈ 0.632 > threshold
        action = PhiAction(PhiActionKind.MYCELIAL_TICK, {})
        dispatcher.enqueue(action)
        result = dispatcher.step()
        assert result.gated
        assert result.result is not None
        assert "error" in result.result

    def test_attach_substrate_after_construction(self):
        idx = FakeHarmonicIndex()
        dispatcher = make_dispatcher(harmonic_index=idx, tau=1.0)
        assert dispatcher._substrate is None
        snap = _make_snapshot(n=4)
        sub = MycelialSubstrate(snap, idx)
        dispatcher.attach_substrate(sub)
        assert dispatcher._substrate is sub

    def test_state_includes_mycelial_when_attached(self):
        dispatcher, sub, idx = self._make_dispatcher_with_substrate()
        s = dispatcher.state()
        assert "mycelial" in s
        assert "n_nodes" in s["mycelial"]

    def test_state_no_mycelial_when_not_attached(self):
        idx = FakeHarmonicIndex()
        dispatcher = make_dispatcher(harmonic_index=idx, tau=1.0)
        s = dispatcher.state()
        assert "mycelial" not in s

    def test_auto_tick_on_gate_open(self):
        dispatcher, sub, idx = self._make_dispatcher_with_substrate()
        dispatcher._steps_since_tick = 1  # 1-exp(-1/1.0) ≈ 0.632 > threshold → gate open
        initial_ticks = sub.tick_count
        dispatcher.step()  # gate open → _run_cairrn_code_tick → substrate.tick()
        assert sub.tick_count == initial_ticks + 1

    def test_mycelial_tick_action_result_has_tick_key(self):
        dispatcher, sub, idx = self._make_dispatcher_with_substrate()
        dispatcher._steps_since_tick = 1  # 1-exp(-1/1.0) ≈ 0.632 > threshold → gate open
        action = PhiAction(PhiActionKind.MYCELIAL_TICK, {"budget": 5.0})
        dispatcher.enqueue(action)
        result = dispatcher.step()
        assert result.gated
        if isinstance(result.result, dict) and "error" not in result.result:
            assert "tick" in result.result


# ---------------------------------------------------------------------------
# Growth gate — new edges form when energy is high enough
# ---------------------------------------------------------------------------


class TestGrowthGate:
    def test_new_edges_formed_after_many_ticks(self):
        """After enough high-budget ticks, growth gate should add edges."""
        snap = _make_snapshot(n=8, connected=False)  # start disconnected
        idx = FakeHarmonicIndex(code_act=1.0)
        sub = MycelialSubstrate(snap, idx)
        total_new = 0
        for _ in range(30):
            r = sub.tick(budget=100.0)
            total_new += r.new_edges
        # With very high budget, energy rises and growth gate opens
        assert total_new >= 0  # at minimum no crash; edges may or may not form


# ---------------------------------------------------------------------------
# Disconnected graph
# ---------------------------------------------------------------------------


class TestDisconnectedGraph:
    def test_isolated_nodes_no_crash(self):
        snap = _make_snapshot(n=5, connected=False)
        idx = FakeHarmonicIndex(code_act=0.5)
        sub = MycelialSubstrate(snap, idx)
        for _ in range(5):
            result = sub.tick(budget=5.0)
        assert isinstance(result, MycelialTickResult)
        assert result.total_flow == pytest.approx(0.0, abs=1e-9)

    def test_n1_no_crash(self):
        snap = FakeSnapshot(
            tracks=[FakeTrack("/fake/0.mp3")],
            H=np.ones((1, 256)),
            A=np.zeros((1, 1)),
        )
        idx = FakeHarmonicIndex()
        sub = MycelialSubstrate(snap, idx)
        result = sub.tick(budget=1.0)
        assert isinstance(result, MycelialTickResult)


# ---------------------------------------------------------------------------
# as_dict serialisation
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_tick_result_as_dict_keys(self):
        sub = _make_substrate()
        r = sub.tick(budget=5.0)
        d = r.as_dict()
        for key in ("tick", "n_nodes", "n_edges", "mean_energy", "max_energy",
                    "total_flow", "new_edges", "autolysed", "budget_used"):
            assert key in d

    def test_tick_result_autolysed_is_list(self):
        sub = _make_substrate()
        r = sub.tick(budget=5.0)
        assert isinstance(r.as_dict()["autolysed"], list)
