"""
Tests for PhiTracerSession — the OctopusTracer/phi wiring.

All tests use synthetic PhiGraph (no disk I/O) and a real TracerDaemon.
Integration tests at the bottom require the actual library.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from engine.phi_session import PhiTracerSession, make_phi_session
from engine.tracer_daemon import TracerDaemon, TracerSummary
from phi.graph.phi_graph import PhiGraph, PhiGraphSnapshot
from phi.library import Track, PhiLibrary


# ============================================================================
# Helpers
# ============================================================================

def make_snap(N: int = 10, d: int = 256, seed: int = 0) -> PhiGraphSnapshot:
    """Synthetic PhiGraphSnapshot with random H and sparse A."""
    rng = np.random.default_rng(seed)
    H = rng.standard_normal((N, d))
    norms = np.linalg.norm(H, axis=1, keepdims=True)
    H = H / np.where(norms < 1e-12, 1e-12, norms)
    A = np.zeros((N, N))
    for i in range(N):
        A[i, (i + 1) % N] = 1.0
        A[(i + 1) % N, i] = 1.0
    tracks = [
        Track(path=Path(f"/fake/T{i}.mp3"), json_path=Path(f"/fake/T{i}.json"))
        for i in range(N)
    ]
    return PhiGraphSnapshot(tracks=tracks, H=H, A=A)


def make_session(N: int = 10, seed: int = 0) -> PhiTracerSession:
    """Session with a synthetic snapshot pre-loaded (build() already called)."""
    snap = make_snap(N=N, seed=seed)
    # Mock PhiGraph so build() returns our synthetic snap
    mock_graph = MagicMock(spec=PhiGraph)
    mock_graph.build.return_value = snap

    daemon = TracerDaemon(
        max_tracers=8,
        tick_gate_interval=4,
        d=256,
        coherence_tau=10.0,
        vault_root=None,
    )
    session = PhiTracerSession(phi_graph=mock_graph, daemon=daemon)
    session.build()   # populates self._snap via mock_graph.build()
    return session


# ============================================================================
# PhiTracerSession construction
# ============================================================================

class TestPhiTracerSessionConstruction:
    def test_snapshot_none_before_build(self):
        mock_graph = MagicMock(spec=PhiGraph)
        daemon = TracerDaemon()
        s = PhiTracerSession(phi_graph=mock_graph, daemon=daemon)
        assert s.snapshot is None

    def test_n_tracks_zero_before_build(self):
        mock_graph = MagicMock(spec=PhiGraph)
        daemon = TracerDaemon()
        s = PhiTracerSession(phi_graph=mock_graph, daemon=daemon)
        assert s.n_tracks == 0

    def test_tick_raises_before_build(self):
        mock_graph = MagicMock(spec=PhiGraph)
        daemon = TracerDaemon()
        s = PhiTracerSession(phi_graph=mock_graph, daemon=daemon)
        with pytest.raises(RuntimeError, match="build\\(\\)"):
            s.tick()

    def test_build_populates_snapshot(self):
        s = make_session(N=8)
        assert s.snapshot is not None
        assert s.snapshot.N == 8

    def test_n_tracks_after_build(self):
        s = make_session(N=12)
        assert s.n_tracks == 12

    def test_repr_after_build(self):
        s = make_session(N=6)
        r = repr(s)
        assert "tracks=6" in r


# ============================================================================
# Tick contract
# ============================================================================

class TestPhiTracerSessionTick:
    def test_tick_returns_tracer_summary(self):
        s = make_session()
        result = s.tick()
        assert isinstance(result, TracerSummary)

    def test_tick_increments_daemon_tick(self):
        s = make_session()
        assert s.daemon_tick == 0
        s.tick()
        assert s.daemon_tick == 1
        s.tick()
        assert s.daemon_tick == 2

    def test_cold_start_spawns_tracer(self):
        s = make_session()
        s.tick()
        # First tick → COLD_START → 1 tracer
        assert s.n_tracers >= 1

    def test_tracer_count_bounded_by_max(self):
        s = make_session()
        # Run many ticks and confirm tracers never exceed max_tracers
        for _ in range(30):
            s.tick()
        assert s.n_tracers <= s.daemon.max_tracers

    def test_summary_fields_populated(self):
        s = make_session()
        summ = s.tick()
        assert hasattr(summ, "arm_sprout")
        assert hasattr(summ, "arm_prune")
        assert hasattr(summ, "mean_coherence")
        assert hasattr(summ, "n_tracers")

    def test_summary_arm_scores_finite(self):
        s = make_session()
        summ = s.tick()
        for field in ("arm_sprout", "arm_prune", "arm_graft", "arm_cluster",
                      "arm_rank", "arm_tag", "arm_resurface", "arm_merge"):
            assert np.isfinite(getattr(summ, field)), f"{field} not finite"

    def test_multiple_ticks_stable(self):
        s = make_session(N=15)
        for _ in range(10):
            summ = s.tick()
            assert summ.n_tracers >= 0


# ============================================================================
# refresh_and_tick
# ============================================================================

class TestRefreshAndTick:
    def test_refresh_calls_build(self):
        mock_graph = MagicMock(spec=PhiGraph)
        snap = make_snap(N=6)
        mock_graph.build.return_value = snap

        daemon = TracerDaemon(d=256)
        s = PhiTracerSession(phi_graph=mock_graph, daemon=daemon)
        s.build()
        assert mock_graph.build.call_count == 1

        s.refresh_and_tick()
        assert mock_graph.build.call_count == 2

    def test_refresh_and_tick_returns_summary(self):
        s = make_session(N=8)
        result = s.refresh_and_tick()
        assert isinstance(result, TracerSummary)

    def test_refresh_updates_snapshot(self):
        snap_a = make_snap(N=5, seed=1)
        snap_b = make_snap(N=7, seed=2)  # different shape
        mock_graph = MagicMock(spec=PhiGraph)
        mock_graph.build.side_effect = [snap_a, snap_b]

        daemon = TracerDaemon(d=256)
        s = PhiTracerSession(phi_graph=mock_graph, daemon=daemon)
        s.build()
        assert s.n_tracks == 5

        # refresh_and_tick swaps in snap_b
        # (daemon d=256 still matches snap_b's H shape)
        s.refresh_and_tick()
        assert s.n_tracks == 7


# ============================================================================
# Harmonic index integration
# ============================================================================

class TestHarmonicIndexIntegration:
    def test_harmonic_index_changes_after_tick(self):
        s = make_session(N=10)
        acts_before = [sh.activation for sh in s.harmonic_index.shards]
        s.tick()
        acts_after = [sh.activation for sh in s.harmonic_index.shards]
        # At least one shard should change after arm scores are injected
        assert any(a != b for a, b in zip(acts_before, acts_after))

    def test_bridge_tick_advances(self):
        s = make_session(N=8)
        assert s.bridge._tick == 0
        s.tick()
        assert s.bridge._tick == 1

    def test_harmonic_activations_bounded(self):
        s = make_session(N=10)
        for _ in range(5):
            s.tick()
        for shard in s.harmonic_index.shards:
            assert np.isfinite(shard.activation)


# ============================================================================
# make_phi_session factory
# ============================================================================

class TestMakePhiSession:
    def test_returns_phi_tracer_session(self):
        from phi.library import LIBRARY_ROOT
        if not LIBRARY_ROOT.exists():
            pytest.skip("Library root not found")
        s = make_phi_session()
        assert isinstance(s, PhiTracerSession)

    def test_snapshot_none_before_build(self):
        from phi.library import LIBRARY_ROOT
        if not LIBRARY_ROOT.exists():
            pytest.skip("Library root not found")
        s = make_phi_session()
        assert s.snapshot is None

    def test_d_matches_clap_proj_output(self):
        """TracerDaemon d must equal CLAPProjection D_OUT=256."""
        from phi.library import LIBRARY_ROOT
        if not LIBRARY_ROOT.exists():
            pytest.skip("Library root not found")
        s = make_phi_session()
        assert s.daemon.d == 256

    def test_custom_edge_threshold(self):
        from phi.library import LIBRARY_ROOT
        if not LIBRARY_ROOT.exists():
            pytest.skip("Library root not found")
        s = make_phi_session(edge_threshold=0.30)
        assert s.phi_graph.edge_threshold == 0.30

    def test_custom_max_tracers(self):
        from phi.library import LIBRARY_ROOT
        if not LIBRARY_ROOT.exists():
            pytest.skip("Library root not found")
        s = make_phi_session(max_tracers=4)
        assert s.daemon.max_tracers == 4


# ============================================================================
# Integration — real library build + tick
# ============================================================================

@pytest.mark.integration
class TestPhiSessionRealLibrary:
    def test_build_and_tick(self):
        from phi.library import LIBRARY_ROOT
        if not LIBRARY_ROOT.exists():
            pytest.skip("Library root not found")
        s = make_phi_session()
        s.build()
        assert s.n_tracks > 0
        summ = s.tick()
        assert isinstance(summ, TracerSummary)
        assert summ.n_tracers >= 1

    def test_three_ticks_stable(self):
        from phi.library import LIBRARY_ROOT
        if not LIBRARY_ROOT.exists():
            pytest.skip("Library root not found")
        s = make_phi_session()
        s.build()
        for _ in range(3):
            summ = s.tick()
            assert all(
                np.isfinite(v)
                for v in summ.as_dict().values()
            )
