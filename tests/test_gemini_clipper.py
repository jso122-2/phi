"""
Tests for GeminiClipper — phi/models/gemini_clipper.py.

Uses synthetic Track + PhiGraphSnapshot (no disk I/O, no real library).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from phi._track import Track
from phi.graph._snapshot import PhiGraphSnapshot
from phi.models._metadata_encoder import MetadataEncoder
from phi.models.clap_proj import CLAPProjection, D_OUT
from phi.models.gemini_clipper import (
    GeminiClipper,
    ClipResult,
    ClippedTrack,
    _track_text,
    _query_h_vec,
)


# ============================================================================
# Helpers
# ============================================================================


def make_track(
    name: str = "TestTrack",
    artist: str = "Artist",
    lfm_tags: list[str] | None = None,
    duration_s: float = 200.0,
    album: str = "",
    year: str = "",
    key: str = "C",
) -> Track:
    return Track(
        path=Path(f"/fake/{name}.mp3"),
        json_path=Path(f"/fake/{name}.json"),
        name=name,
        artist=artist,
        lfm_tags=lfm_tags if lfm_tags is not None else ["soul"],
        duration_s=duration_s,
        album=album,
        year=year,
        key=key,
    )


def make_snap(tracks: list[Track], rng_seed: int = 0) -> PhiGraphSnapshot:
    rng = np.random.default_rng(rng_seed)
    N = len(tracks)
    H = rng.standard_normal((N, D_OUT))
    norms = np.linalg.norm(H, axis=1, keepdims=True)
    H = H / np.where(norms < 1e-12, 1.0, norms)
    A = np.zeros((N, N))
    return PhiGraphSnapshot(tracks=tracks, H=H, A=A)


def make_clipper(top_k: int = 3, alpha: float = 0.5) -> tuple[GeminiClipper, MetadataEncoder, CLAPProjection]:
    proj = CLAPProjection(rng=np.random.default_rng(42))
    enc = MetadataEncoder()
    enc.set_vocab(["soul", "jazz", "techno", "electronic", "pop", "rock", "ambient"])
    clipper = GeminiClipper(proj=proj, encoder=enc, top_k=top_k, alpha=alpha)
    return clipper, enc, proj


# ============================================================================
# _track_text
# ============================================================================


class TestTrackText:
    def test_includes_name_and_artist(self):
        t = make_track(name="Midnight Rain", artist="Bonobo")
        text = _track_text(t)
        assert "Midnight Rain" in text
        assert "Bonobo" in text

    def test_includes_tags(self):
        t = make_track(lfm_tags=["ambient", "electronic"])
        text = _track_text(t)
        assert "ambient" in text
        assert "electronic" in text

    def test_empty_track_no_crash(self):
        t = Track(path=Path("/empty.mp3"), json_path=Path("/empty.json"))
        text = _track_text(t)
        assert isinstance(text, str)


# ============================================================================
# _query_h_vec
# ============================================================================


class TestQueryHVec:
    def test_output_shape(self):
        proj = CLAPProjection()
        enc = MetadataEncoder()
        enc.set_vocab(["soul", "jazz"])
        h = _query_h_vec("soul jazz music", enc, proj)
        assert h.shape == (D_OUT,)

    def test_l2_normalised(self):
        proj = CLAPProjection()
        enc = MetadataEncoder()
        enc.set_vocab(["soul", "jazz"])
        h = _query_h_vec("soul jazz music", enc, proj)
        np.testing.assert_allclose(np.linalg.norm(h), 1.0, atol=1e-10)

    def test_empty_query_no_crash(self):
        proj = CLAPProjection()
        enc = MetadataEncoder()
        enc.set_vocab(["soul"])
        h = _query_h_vec("", enc, proj)
        assert h.shape == (D_OUT,)
        assert not np.any(np.isnan(h))


# ============================================================================
# GeminiClipper
# ============================================================================


class TestGeminiClipper:
    def _run(self, n: int = 8, query: str = "soul jazz", top_k: int = 3) -> ClipResult:
        tracks = [
            make_track(name=f"T{i}", lfm_tags=["soul"] if i % 2 == 0 else ["techno"])
            for i in range(n)
        ]
        snap = make_snap(tracks)
        clipper, _, _ = make_clipper(top_k=top_k)
        return clipper.clip(query, snap)

    def test_returns_clip_result(self):
        result = self._run()
        assert isinstance(result, ClipResult)

    def test_top_k_length(self):
        result = self._run(n=8, top_k=3)
        assert len(result.top_k) == 3

    def test_top_k_capped_to_n(self):
        # top_k > N → only N returned
        result = self._run(n=4, top_k=10)
        assert len(result.top_k) == 4

    def test_ranks_are_sequential(self):
        result = self._run()
        for i, ct in enumerate(result.top_k):
            assert ct.rank == i

    def test_p_sps_descending(self):
        result = self._run(n=10, top_k=5)
        scores = [ct.p_sps for ct in result.top_k]
        assert scores == sorted(scores, reverse=True)

    def test_scores_in_unit_range(self):
        result = self._run(n=8, top_k=4)
        for ct in result.top_k:
            assert 0.0 <= ct.semantic_score <= 1.0
            assert 0.0 <= ct.h_space_score <= 1.0
            assert 0.0 <= ct.p_sps <= 1.0

    def test_context_contains_query(self):
        result = self._run(query="soul jazz")
        assert "soul jazz" in result.context

    def test_context_contains_track_names(self):
        tracks = [make_track(name="BlueSong", lfm_tags=["soul"])]
        snap = make_snap(tracks)
        clipper, _, _ = make_clipper(top_k=1)
        result = clipper.clip("soul music", snap)
        assert "BlueSong" in result.context

    def test_n_tracks_searched(self):
        result = self._run(n=12, top_k=3)
        assert result.n_tracks_searched == 12

    def test_alpha_stored(self):
        clipper, _, _ = make_clipper(alpha=0.3)
        tracks = [make_track()]
        snap = make_snap(tracks)
        result = clipper.clip("soul", snap)
        assert result.alpha == pytest.approx(0.3)

    def test_pure_semantic_alpha_zero(self):
        """alpha=0 → P_sps == semantic_score for every track."""
        clipper, _, _ = make_clipper(top_k=3, alpha=0.0)
        tracks = [make_track(name=f"T{i}", lfm_tags=["soul"]) for i in range(5)]
        snap = make_snap(tracks)
        result = clipper.clip("soul", snap)
        for ct in result.top_k:
            assert abs(ct.p_sps - ct.semantic_score) < 1e-4

    def test_pure_hspace_alpha_one(self):
        """alpha=1 → P_sps == h_space_score for every track."""
        clipper, _, _ = make_clipper(top_k=3, alpha=1.0)
        tracks = [make_track(name=f"T{i}", lfm_tags=["soul"]) for i in range(5)]
        snap = make_snap(tracks)
        result = clipper.clip("soul", snap)
        for ct in result.top_k:
            assert abs(ct.p_sps - ct.h_space_score) < 1e-4

    def test_empty_snap_returns_no_tracks(self):
        snap = PhiGraphSnapshot(
            tracks=[],
            H=np.zeros((0, D_OUT)),
            A=np.zeros((0, 0)),
        )
        clipper, _, _ = make_clipper()
        result = clipper.clip("jazz", snap)
        assert result.top_k == []
        assert result.n_tracks_searched == 0

    def test_single_track_snap(self):
        tracks = [make_track(name="Lonely", lfm_tags=["ambient"])]
        snap = make_snap(tracks)
        clipper, _, _ = make_clipper(top_k=5)
        result = clipper.clip("ambient music", snap)
        assert len(result.top_k) == 1
        assert result.top_k[0].track.name == "Lonely"

    def test_repr(self):
        clipper, _, _ = make_clipper(top_k=7, alpha=0.4)
        r = repr(clipper)
        assert "top_k=7" in r
        assert "0.4" in r

    def test_context_block_format(self):
        tracks = [make_track(name="Echo", artist="Four Tet", lfm_tags=["electronic"])]
        snap = make_snap(tracks)
        clipper, _, _ = make_clipper(top_k=1)
        result = clipper.clip("electronic", snap)
        assert "[1]" in result.context
        assert "Four Tet" in result.context
        assert "Tags:" in result.context
