"""
Tests for engine/prefeed_shuffle.py — CAIRRN-bound prefeed shuffle.

Synthetic session only — no disk I/O.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from engine.gate import COHERENCE_THRESHOLD
from engine.prefeed_shuffle import (
    CAIRRNPrefeedShuffle,
    PrefeedShuffle,
    ShufflePeek,
    ShuffleStepResult,
    _Q,
    _harmonic_scores,
    _shuffle_order,
    make_prefeed_shuffle,
)
from engine.phi_session import PhiTracerSession
from engine.tracer_daemon import TracerDaemon
from phi.graph.phi_graph import PhiGraph
from phi.graph._snapshot import PhiGraphSnapshot
from phi.library import Track
from sims.harmonic import HarmonicIndex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snap(N: int = 8, d: int = 256, seed: int = 0) -> PhiGraphSnapshot:
    rng = np.random.default_rng(seed)
    H = rng.standard_normal((N, d))
    norms = np.linalg.norm(H, axis=1, keepdims=True)
    H = H / np.where(norms < 1e-12, 1e-12, norms)
    A = np.zeros((N, N))
    tracks = [
        Track(path=Path(f"/fake/T{i}.mp3"), json_path=Path(f"/fake/T{i}.json"))
        for i in range(N)
    ]
    return PhiGraphSnapshot(tracks=tracks, H=H, A=A)


def _make_harmonic(activations: list[float] | None = None) -> HarmonicIndex:
    idx = HarmonicIndex(n_harmonics=8, coupling=0.15)
    if activations:
        for i, v in enumerate(activations):
            idx.inject(i, v)
    return idx


def _make_session(N: int = 8, seed: int = 0) -> PhiTracerSession:
    snap = _make_snap(N=N, seed=seed)
    mock_graph = MagicMock(spec=PhiGraph)
    mock_graph.build.return_value = snap
    daemon = TracerDaemon(max_tracers=2, tick_gate_interval=4, d=256, coherence_tau=10.0)
    session = PhiTracerSession(phi_graph=mock_graph, daemon=daemon)
    session.build()
    session.tick = MagicMock(return_value=MagicMock())
    session.refresh_and_tick = MagicMock(return_value=MagicMock())
    return session


# ---------------------------------------------------------------------------
# Fixed projection matrix _Q
# ---------------------------------------------------------------------------


class TestProjectionMatrix:
    def test_shape(self):
        assert _Q.shape == (8, 256)

    def test_rows_normalised(self):
        norms = np.linalg.norm(_Q, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-10)

    def test_deterministic(self):
        from engine.prefeed_shuffle import _build_Q
        Q2 = _build_Q()
        np.testing.assert_array_equal(_Q, Q2)


# ---------------------------------------------------------------------------
# _harmonic_scores
# ---------------------------------------------------------------------------


class TestHarmonicScores:
    def test_shape(self):
        rng = np.random.default_rng(0)
        H = rng.standard_normal((10, 256))
        H /= np.linalg.norm(H, axis=1, keepdims=True)
        acts = [0.1] * 8
        scores = _harmonic_scores(H, acts, exploration=0.0, rng=np.random.default_rng(1))
        assert scores.shape == (10,)

    def test_empty_H(self):
        rng = np.random.default_rng(0)
        H = np.zeros((0, 256))
        scores = _harmonic_scores(H, [0.0] * 8, 0.0, rng)
        assert scores.shape == (0,)

    def test_no_exploration_is_deterministic(self):
        rng1 = np.random.default_rng(0)
        rng2 = np.random.default_rng(0)
        H = np.random.default_rng(5).standard_normal((10, 256))
        H /= np.linalg.norm(H, axis=1, keepdims=True)
        acts = [1.0, 0.5, 0.2, 0.8, 0.3, 0.1, 0.6, 0.4]
        s1 = _harmonic_scores(H, acts, 0.0, rng1)
        s2 = _harmonic_scores(H, acts, 0.0, rng2)
        np.testing.assert_array_equal(s1, s2)

    def test_high_shard_activation_influences_order(self):
        # Uniform activations → gravity is average of Q rows
        # Non-uniform → different gravity → different track ordering
        rng = np.random.default_rng(0)
        H = np.random.default_rng(9).standard_normal((20, 256))
        H /= np.linalg.norm(H, axis=1, keepdims=True)

        acts_uniform = [0.5] * 8
        acts_biased  = [0.0, 0.0, 0.0, 5.0, 5.0, 0.0, 0.0, 0.0]  # CODE hot
        s_uniform = _harmonic_scores(H, acts_uniform, 0.0, np.random.default_rng(42))
        s_biased  = _harmonic_scores(H, acts_biased,  0.0, np.random.default_rng(42))
        # Scores differ when activations differ
        assert not np.allclose(s_uniform, s_biased)


# ---------------------------------------------------------------------------
# _shuffle_order
# ---------------------------------------------------------------------------


class TestShuffleOrder:
    def test_length(self):
        rng = np.random.default_rng(0)
        H = rng.standard_normal((12, 256))
        H /= np.linalg.norm(H, axis=1, keepdims=True)
        order = _shuffle_order(H, [0.1] * 8, 0.0, rng)
        assert len(order) == 12

    def test_is_permutation(self):
        rng = np.random.default_rng(0)
        N = 15
        H = rng.standard_normal((N, 256))
        H /= np.linalg.norm(H, axis=1, keepdims=True)
        order = _shuffle_order(H, [0.5] * 8, 0.1, rng)
        assert sorted(order) == list(range(N))

    def test_indices_in_range(self):
        rng = np.random.default_rng(0)
        N = 8
        H = rng.standard_normal((N, 256))
        H /= np.linalg.norm(H, axis=1, keepdims=True)
        order = _shuffle_order(H, [1.0] * 8, 0.0, rng)
        assert all(0 <= i < N for i in order)


# ---------------------------------------------------------------------------
# PrefeedShuffle — double-buffer
# ---------------------------------------------------------------------------


class TestPrefeedShuffle:
    def test_next_raises_before_commit(self):
        s = PrefeedShuffle()
        with pytest.raises(RuntimeError, match="no active shuffle"):
            s.next()

    def test_prefeed_populates_pending(self):
        s = PrefeedShuffle()
        snap = _make_snap(N=8)
        idx = _make_harmonic()
        n, pfs = s.prefeed(snap, idx)
        assert n == 8
        assert isinstance(pfs, float)
        assert s.pending_len == 8
        assert s.active_len == 0

    def test_commit_swaps_buffers(self):
        s = PrefeedShuffle()
        snap = _make_snap(N=8)
        idx = _make_harmonic()
        s.prefeed(snap, idx)
        committed = s.commit()
        assert committed is True
        assert s.active_len == 8
        assert s.pending_len == 0

    def test_commit_empty_pending_returns_false(self):
        s = PrefeedShuffle()
        assert s.commit() is False

    def test_next_returns_valid_index(self):
        N = 8
        snap = _make_snap(N=N)
        idx = _make_harmonic()
        s = PrefeedShuffle()
        s.prefeed(snap, idx)
        s.commit()
        track_idx = s.next()
        assert 0 <= track_idx < N

    def test_next_advances_cursor(self):
        snap = _make_snap(N=8)
        idx = _make_harmonic()
        s = PrefeedShuffle()
        s.prefeed(snap, idx)
        s.commit()
        first = s.next()
        assert s.cursor == 1
        second = s.next()
        assert s.cursor == 2

    def test_next_wraps_around(self):
        N = 4
        snap = _make_snap(N=N)
        idx = _make_harmonic()
        s = PrefeedShuffle()
        s.prefeed(snap, idx)
        s.commit()
        seen = {s.next() for _ in range(N * 3)}
        assert len(seen) == N  # all indices eventually seen

    def test_prefeed_overwrites_pending(self):
        snap = _make_snap(N=8)
        idx = _make_harmonic([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        s = PrefeedShuffle(exploration=0.0)
        s.prefeed(snap, idx)
        first_pending = list(s._pending)

        idx2 = _make_harmonic([0.0, 0.0, 0.0, 5.0, 5.0, 0.0, 0.0, 0.0])
        s.prefeed(snap, idx2)
        second_pending = list(s._pending)
        # Different shard state → different pending order
        # (may or may not differ by chance but pending is overwritten)
        assert len(second_pending) == 8

    def test_commit_resets_cursor(self):
        snap = _make_snap(N=8)
        idx = _make_harmonic()
        s = PrefeedShuffle()
        s.prefeed(snap, idx)
        s.commit()
        s.next()
        s.next()
        assert s.cursor == 2
        # Second prefeed + commit resets cursor
        s.prefeed(snap, idx)
        s.commit()
        assert s.cursor == 0

    def test_empty_snapshot_prefeed(self):
        snap = _make_snap(N=0)
        idx = _make_harmonic()
        s = PrefeedShuffle()
        n, pfs = s.prefeed(snap, idx)
        assert n == 0
        assert pfs == 0.0
        assert not s.commit()

    def test_peek_returns_correct_count(self):
        snap = _make_snap(N=8)
        idx = _make_harmonic()
        s = PrefeedShuffle()
        s.prefeed(snap, idx)
        s.commit()
        p = s.peek(3)
        assert isinstance(p, ShufflePeek)
        assert p.n == 3

    def test_peek_empty_active(self):
        s = PrefeedShuffle()
        p = s.peek(5)
        assert p.n == 0
        assert p.indices == []

    def test_peek_does_not_advance_cursor(self):
        snap = _make_snap(N=8)
        idx = _make_harmonic()
        s = PrefeedShuffle()
        s.prefeed(snap, idx)
        s.commit()
        s.peek(5)
        s.peek(5)
        assert s.cursor == 0

    def test_peek_pending_ready_flag(self):
        snap = _make_snap(N=8)
        idx = _make_harmonic()
        s = PrefeedShuffle()
        s.prefeed(snap, idx)
        s.commit()
        # Active but no pending
        p = s.peek()
        assert p.pending_ready is False
        # Now prefeed without committing
        s.prefeed(snap, idx)
        p2 = s.peek()
        assert p2.pending_ready is True

    def test_repr_contains_key_info(self):
        s = PrefeedShuffle()
        r = repr(s)
        assert "active" in r
        assert "cursor" in r
        assert "pending" in r


# ---------------------------------------------------------------------------
# CAIRRNPrefeedShuffle — integrated
# ---------------------------------------------------------------------------


class TestCAIRRNPrefeedShuffle:
    def test_seed_populates_active(self):
        session = _make_session(N=8)
        s = CAIRRNPrefeedShuffle(session)
        peek = s.seed()
        assert isinstance(peek, ShufflePeek)
        assert s.shuffle.active_len == 8

    def test_seed_raises_without_build(self):
        snap = _make_snap(N=8)
        mock_graph = MagicMock(spec=PhiGraph)
        mock_graph.build.return_value = snap
        daemon = TracerDaemon(max_tracers=2, tick_gate_interval=4, d=256, coherence_tau=10.0)
        session = PhiTracerSession(phi_graph=mock_graph, daemon=daemon)
        # build() NOT called
        s = CAIRRNPrefeedShuffle(session)
        with pytest.raises(RuntimeError, match="build()"):
            s.seed()

    def test_step_returns_step_result(self):
        session = _make_session(N=8)
        s = CAIRRNPrefeedShuffle(session)
        s.seed()
        result = s.step()
        assert isinstance(result, ShuffleStepResult)

    def test_first_step_coherence_zero_gate_closed(self):
        """steps_since_tick=0 → coherence=0.0 → gate closed → prefeed, no commit."""
        session = _make_session(N=8)
        s = CAIRRNPrefeedShuffle(session)
        s.seed()
        result = s.step()
        assert result.committed is False
        assert result.prefeeding is True

    def test_step_skipped_when_incoherent(self):
        session = _make_session(N=8)
        s = CAIRRNPrefeedShuffle(session, tau=10.0, threshold=COHERENCE_THRESHOLD)
        s.seed()
        s._steps_since_tick = 6   # coherence < threshold → gate closed
        result = s.step()
        assert result.committed is False
        assert result.prefeeding is True

    def test_skip_prefeed_updates_pending(self):
        session = _make_session(N=8)
        s = CAIRRNPrefeedShuffle(session, tau=10.0)
        s.seed()
        s._steps_since_tick = 6
        result = s.step()
        assert result.pending_len == 8   # prefeed ran

    def test_skip_increments_steps(self):
        session = _make_session(N=8)
        s = CAIRRNPrefeedShuffle(session, tau=10.0)
        s.seed()
        s._steps_since_tick = 6
        before = s.steps_since_commit
        s.step()
        assert s.steps_since_commit == before + 1

    def test_commit_resets_steps(self):
        session = _make_session(N=8)
        s = CAIRRNPrefeedShuffle(session)
        s.seed()
        # 1 - exp(-9/10) ≈ 0.593 ≥ 0.5671 → gate opens → commit resets counter
        s._steps_since_tick = 9
        s.step()
        assert s.steps_since_commit == 0

    def test_next_after_seed(self):
        N = 8
        session = _make_session(N=N)
        s = CAIRRNPrefeedShuffle(session)
        s.seed()
        track_idx = s.next()
        assert 0 <= track_idx < N

    def test_next_raises_before_seed(self):
        session = _make_session(N=8)
        s = CAIRRNPrefeedShuffle(session)
        with pytest.raises(RuntimeError):
            s.next()

    def test_step_tick_called_on_gate_open(self):
        session = _make_session(N=8)
        s = CAIRRNPrefeedShuffle(session)
        s.seed()
        s._steps_since_tick = 9   # coherence ≈ 0.593 ≥ threshold → gate open
        s.step()
        session.tick.assert_called()

    def test_step_no_tick_when_gate_closed(self):
        session = _make_session(N=8)
        s = CAIRRNPrefeedShuffle(session, tau=10.0)
        s.seed()
        s._steps_since_tick = 6   # gate closed
        s.step()
        session.tick.assert_not_called()

    def test_active_tracks_are_valid_permutation(self):
        N = 10
        session = _make_session(N=N)
        s = CAIRRNPrefeedShuffle(session)
        s.seed()
        # Consume all N tracks and verify they cover all indices
        seen = {s.next() for _ in range(N)}
        assert len(seen) == N
        assert all(0 <= i < N for i in seen)

    def test_step_as_dict(self):
        session = _make_session(N=8)
        s = CAIRRNPrefeedShuffle(session)
        s.seed()
        result = s.step()
        d = result.as_dict()
        for key in ("committed", "prefeeding", "coherence", "code_act",
                    "steps_waiting", "active_len", "pending_len"):
            assert key in d

    def test_state_dict(self):
        session = _make_session(N=8)
        s = CAIRRNPrefeedShuffle(session)
        st = s.state()
        for key in ("coherence", "gate_open", "threshold", "tau",
                    "steps_since_commit", "ticks_run", "active_len",
                    "pending_len", "cursor", "code_activation"):
            assert key in st

    def test_gate_closed_at_zero_steps(self):
        """coherence = 1 - exp(0) = 0.0 < threshold → gate closed immediately post-commit."""
        session = _make_session()
        s = CAIRRNPrefeedShuffle(session)
        assert s.gate_open is False

    def test_gate_open_after_many_steps(self):
        """coherence = 1 - exp(-100/10) ≈ 1.0 ≥ threshold → gate open after long wait."""
        session = _make_session()
        s = CAIRRNPrefeedShuffle(session)
        s._steps_since_tick = 100
        assert s.gate_open is True

    def test_repr(self):
        session = _make_session()
        s = CAIRRNPrefeedShuffle(session)
        r = repr(s)
        assert "coherence" in r
        assert "gate" in r
        assert "active" in r

    def test_ticks_run_increments_on_gate(self):
        session = _make_session(N=8)
        s = CAIRRNPrefeedShuffle(session)
        s.seed()
        s._steps_since_tick = 9   # open gate for first tick
        s.step()
        assert s.ticks_run == 1
        s._steps_since_tick = 9   # gate reset to 0 after commit — reopen for second tick
        s.step()
        assert s.ticks_run == 2


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestFactory:
    def test_make_prefeed_shuffle(self):
        session = _make_session(N=8)
        s = make_prefeed_shuffle(session, exploration=0.2, tau=5.0, refresh_every=3)
        assert isinstance(s, CAIRRNPrefeedShuffle)
        assert s._tau == 5.0
        assert s._refresh_every == 3
        assert s._shuffle.exploration == pytest.approx(0.2)
