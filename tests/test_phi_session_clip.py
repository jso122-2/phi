"""
Tests for PhiTracerSession.clip() — GeminiClipper integration.

All tests use synthetic data: no disk I/O, no real library.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from engine.phi_session import PhiTracerSession
from engine.tracer_daemon import TracerDaemon
from phi._track import Track
from phi.graph.phi_graph import PhiGraph, PhiGraphSnapshot
from phi.models.clap_proj import CLAPProjection, MetadataEncoder, embed_tracks
from phi.models.gemini_clipper import ClipResult, GeminiClipper


# ============================================================================
# Helpers
# ============================================================================

_TAGS_POOL = ["electronic", "ambient", "techno", "jazz", "dark", "deep", "soul", "indie"]


def make_clip_session(N: int = 8, seed: int = 42) -> PhiTracerSession:
    """
    Session with real CLAPProjection + MetadataEncoder so GeminiClipper
    can encode queries.  build() is NOT called — callers must call it
    explicitly if they want a populated snapshot.
    """
    rng = np.random.default_rng(seed)

    tracks = [
        Track(
            path=Path(f"/fake/T{i}.mp3"),
            json_path=Path(f"/fake/T{i}.json"),
            name=f"Track{i}",
            artist=f"Artist{i % 3}",
            lfm_tags=[_TAGS_POOL[j % len(_TAGS_POOL)] for j in range(i % 3 + 1)],
        )
        for i in range(N)
    ]

    proj = CLAPProjection(rng=rng)
    encoder = MetadataEncoder()
    encoder.set_vocab(_TAGS_POOL)

    X = embed_tracks(tracks, proj, encoder)   # (N, 512)
    H = proj.forward(X)                        # (N, 256) L2-norm
    A = np.zeros((N, N))

    snap = PhiGraphSnapshot(tracks=tracks, H=H, A=A)

    mock_graph = MagicMock(spec=PhiGraph)
    mock_graph.build.return_value = snap
    mock_graph._proj = proj
    mock_graph._encoder = encoder

    daemon = TracerDaemon(
        max_tracers=8,
        tick_gate_interval=4,
        d=256,
        coherence_tau=10.0,
        vault_root=None,
    )
    return PhiTracerSession(phi_graph=mock_graph, daemon=daemon)


def built_session(N: int = 8, seed: int = 42) -> PhiTracerSession:
    """Session with build() already called."""
    s = make_clip_session(N=N, seed=seed)
    s.build()
    return s


# ============================================================================
# clip() pre-build guard
# ============================================================================

class TestClipBeforeBuild:
    def test_raises_runtime_error_before_build(self):
        s = make_clip_session()
        with pytest.raises(RuntimeError, match="build\\(\\)"):
            s.clip("dark ambient")

    def test_clipper_is_none_before_first_clip(self):
        s = built_session()
        assert s._clipper is None


# ============================================================================
# clip() post-build contract
# ============================================================================

class TestClipAfterBuild:
    def test_returns_clip_result(self):
        s = built_session(N=8)
        result = s.clip("dark ambient techno")
        assert isinstance(result, ClipResult)

    def test_clip_result_query_matches_input(self):
        s = built_session(N=8)
        query = "jazzy soul"
        result = s.clip(query)
        assert result.query == query

    def test_n_tracks_searched_matches_track_count(self):
        N = 10
        s = built_session(N=N)
        result = s.clip("electronic", top_k=3)
        assert result.n_tracks_searched == N

    def test_top_k_length_equals_requested_k(self):
        N = 8
        k = 5
        s = built_session(N=N)
        result = s.clip("ambient", top_k=k)
        assert len(result.top_k) == min(k, N)

    def test_top_k_capped_when_k_exceeds_n(self):
        N = 4
        k = 10
        s = built_session(N=N)
        result = s.clip("techno", top_k=k)
        assert len(result.top_k) == N

    def test_default_top_k_is_five(self):
        N = 8
        s = built_session(N=N)
        result = s.clip("deep jazz")
        assert len(result.top_k) == min(5, N)


# ============================================================================
# Lazy clipper creation and caching
# ============================================================================

class TestLazyClipper:
    def test_clipper_none_before_first_clip(self):
        s = built_session()
        assert s._clipper is None

    def test_clipper_created_after_first_clip(self):
        s = built_session()
        s.clip("soul")
        assert s._clipper is not None
        assert isinstance(s._clipper, GeminiClipper)

    def test_same_clipper_reused_for_same_params(self):
        s = built_session()
        s.clip("ambient", top_k=3, alpha=0.5)
        clipper_id = id(s._clipper)
        s.clip("techno", top_k=3, alpha=0.5)
        assert id(s._clipper) == clipper_id

    def test_different_alpha_creates_new_clipper(self):
        s = built_session()
        s.clip("ambient", top_k=3, alpha=0.5)
        first_clipper = s._clipper
        s.clip("ambient", top_k=3, alpha=0.8)
        assert s._clipper is not first_clipper

    def test_different_top_k_creates_new_clipper(self):
        s = built_session()
        s.clip("ambient", top_k=3, alpha=0.5)
        first_clipper = s._clipper
        s.clip("ambient", top_k=7, alpha=0.5)
        assert s._clipper is not first_clipper

    def test_clipper_carries_correct_alpha(self):
        s = built_session()
        s.clip("jazz", top_k=3, alpha=0.3)
        assert abs(s._clipper.alpha - 0.3) < 1e-9

    def test_clipper_carries_correct_top_k(self):
        s = built_session()
        s.clip("jazz", top_k=4, alpha=0.5)
        assert s._clipper.top_k == 4


# ============================================================================
# __repr__ includes clipper state
# ============================================================================

class TestReprClipperField:
    def test_repr_contains_clipper_field(self):
        s = built_session()
        assert "clipper=" in repr(s)

    def test_repr_clipper_none_before_clip(self):
        s = built_session()
        assert "clipper=none" in repr(s)

    def test_repr_clipper_ready_after_clip(self):
        s = built_session()
        s.clip("ambient")
        assert "clipper=ready" in repr(s)
