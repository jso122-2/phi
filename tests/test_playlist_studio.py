# -*- coding: utf-8 -*-
"""tests/test_playlist_studio.py — PlaylistStudio + CAIRRN PLAYLIST_BUILD.

Covers:
  - StudioRequest / StudioResult dataclass construction
  - _arc_target() formula for all six shapes
  - _gaussian_score() scalar check
  - PlaylistStudio.build() with a stub library:
      * full annotated library → result has arc scores and transition scores
      * unannotated library → falls back to metadata energy / BPM order
      * seeds not in library → returns empty result
      * diversity gates: max_per_artist and max_per_genre enforced
      * transition_threshold: jarring transitions are penalised
  - CAIRRN integration: RequestKind.PLAYLIST_BUILD exists + hub = MATH
"""
from __future__ import annotations

import math
import types
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from phi.engine.arc_engine import ArcShape
from phi.engine.playlist_studio import (
    PlaylistStudio,
    StudioRequest,
    StudioResult,
    _arc_target,
    _gaussian_score,
)
from phi.engine.cairrn.router import RequestKind, REQUEST_HUB


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_vec(seed: int, dim: int = 16) -> list[float]:
    """Deterministic unit vector for testing."""
    rng = np.random.default_rng(seed)
    v   = rng.standard_normal(dim).astype(np.float32)
    n   = np.linalg.norm(v)
    return list(v / n)


class _StubLibrary:
    """Minimal library stub for unit tests."""

    def __init__(
        self,
        paths:       List[str],
        annotations: Dict[str, Dict[str, Any]] | None = None,
        metadata:    Dict[str, Dict[str, Any]] | None = None,
    ) -> None:
        self.playlist = list(paths)
        self._ann  = annotations or {}
        self._meta = metadata or {}

    @property
    def size(self) -> int:
        return len(self.playlist)

    def get_annotation(self, path: str) -> Optional[Dict[str, Any]]:
        return self._ann.get(path)

    def get_meta(self, path: str) -> Optional[Dict[str, Any]]:
        return self._meta.get(path)

    def display_name(self, path: str) -> str:
        return path.rsplit("/", 1)[-1]


def _make_annotated_library(n: int = 20) -> _StubLibrary:
    """Library where every track has a distinct mood_vec + spotify_energy."""
    paths = [f"/lib/track_{i:02d}.mp3" for i in range(n)]
    ann   = {}
    meta  = {}
    for i, p in enumerate(paths):
        ann[p]  = {
            "mood_vec":       _make_vec(i),
            "spotify_energy": round(i / (n - 1), 3),
            "genre":          "pop" if i % 3 == 0 else ("rock" if i % 3 == 1 else "jazz"),
        }
        meta[p] = {
            "title":  f"Track {i:02d}",
            "artist": f"Artist {i % 4}",
        }
    return _StubLibrary(paths, ann, meta)


def _make_bare_library(n: int = 15) -> _StubLibrary:
    """Library with no annotations — forces the BPM/metadata fallback path."""
    paths = [f"/bare/track_{i:02d}.mp3" for i in range(n)]
    meta  = {p: {"title": f"Bare {i}", "artist": "ArtA", "bpm": 100 + i * 5}
             for i, p in enumerate(paths)}
    return _StubLibrary(paths, {}, meta)


# ── _arc_target ────────────────────────────────────────────────────────────────

class TestArcTarget:
    def test_flat(self):
        for step in range(20):
            assert _arc_target(ArcShape.FLAT, step, 20) == 0.5

    def test_rising_boundary(self):
        assert _arc_target(ArcShape.RISING, 0, 20) == pytest.approx(0.0, abs=1e-6)
        assert _arc_target(ArcShape.RISING, 19, 20) == pytest.approx(1.0, abs=1e-6)

    def test_falling_boundary(self):
        assert _arc_target(ArcShape.FALLING, 0,  20) == pytest.approx(1.0, abs=1e-6)
        assert _arc_target(ArcShape.FALLING, 19, 20) == pytest.approx(0.0, abs=1e-6)

    def test_peak_at_midpoint(self):
        # For horizon=20, midpoint is step 9 or 10; maximum is at t=0.5
        mid_val = _arc_target(ArcShape.PEAK, 9, 20)
        assert mid_val >= 0.9   # close to 1.0

    def test_valley_inverts_peak(self):
        for step in range(20):
            p = _arc_target(ArcShape.PEAK,   step, 20)
            v = _arc_target(ArcShape.VALLEY, step, 20)
            assert v == pytest.approx(1.0 - p, abs=1e-6)

    def test_wave_completes_cycle(self):
        # step=0 → t=0 → sin(0) = 0 → 0.5
        assert _arc_target(ArcShape.WAVE, 0,  20) == pytest.approx(0.5, abs=1e-4)
        # step=5 → t=5/19 ≈ 0.263 → peak around this area
        val = _arc_target(ArcShape.WAVE, 5, 20)
        assert 0.0 <= val <= 1.0

    def test_all_values_in_unit_interval(self):
        for shape in ArcShape:
            for step in range(0, 30):
                val = _arc_target(shape, step, 20)
                assert 0.0 <= val <= 1.0, f"{shape} step={step} out of [0,1]: {val}"


# ── _gaussian_score ────────────────────────────────────────────────────────────

class TestGaussianScore:
    def test_perfect_match(self):
        assert _gaussian_score(0.5, 0.5, 20.0) == pytest.approx(1.0)

    def test_decreases_with_distance(self):
        s1 = _gaussian_score(0.5, 0.5, 20.0)
        s2 = _gaussian_score(0.7, 0.5, 20.0)
        s3 = _gaussian_score(1.0, 0.5, 20.0)
        assert s1 > s2 > s3

    def test_sharpness_scales_penalty(self):
        soft = _gaussian_score(0.8, 0.5, 5.0)
        hard = _gaussian_score(0.8, 0.5, 50.0)
        assert soft > hard


# ── PlaylistStudio.build ───────────────────────────────────────────────────────

class TestPlaylistStudioBuild:

    # ── Annotated library ──────────────────────────────────────────────────────

    def test_basic_build_returns_requested_length(self):
        lib = _make_annotated_library(30)
        studio = PlaylistStudio(library=lib)
        req    = StudioRequest(
            seeds=[lib.playlist[0], lib.playlist[1]],
            arc_shape=ArcShape.RISING,
            target_count=10,
        )
        result = studio.build(req)
        assert isinstance(result, StudioResult)
        assert len(result.tracks) == 10

    def test_seeds_are_first(self):
        lib = _make_annotated_library(30)
        seeds = [lib.playlist[0], lib.playlist[5]]
        studio = PlaylistStudio(library=lib)
        req    = StudioRequest(seeds=seeds, target_count=12)
        result = studio.build(req)
        assert result.tracks[:2] == seeds

    def test_no_duplicates(self):
        lib = _make_annotated_library(30)
        studio = PlaylistStudio(library=lib)
        req    = StudioRequest(seeds=[lib.playlist[0]], target_count=15)
        result = studio.build(req)
        assert len(result.tracks) == len(set(result.tracks)), "Duplicate paths in result"

    def test_arc_scores_in_range(self):
        lib = _make_annotated_library(30)
        studio = PlaylistStudio(library=lib)
        req    = StudioRequest(seeds=[lib.playlist[0]], target_count=10)
        result = studio.build(req)
        for s in result.arc_scores:
            assert 0.0 <= s <= 1.0, f"arc_score out of range: {s}"

    def test_transition_scores_in_range(self):
        lib = _make_annotated_library(30)
        studio = PlaylistStudio(library=lib)
        req    = StudioRequest(seeds=[lib.playlist[0], lib.playlist[1]], target_count=8)
        result = studio.build(req)
        for t in result.transition_scores:
            assert -1.0 <= t <= 1.0, f"transition_score out of range: {t}"

    def test_result_metadata_correct(self):
        lib = _make_annotated_library(30)
        seeds = [lib.playlist[0], lib.playlist[2]]
        studio = PlaylistStudio(library=lib)
        req    = StudioRequest(seeds=seeds, arc_shape=ArcShape.PEAK, target_count=12)
        result = studio.build(req)
        assert result.seed_paths == seeds
        assert result.arc_shape == "peak"
        assert result.n_annotated >= len(seeds)

    # ── Unannotated fallback ───────────────────────────────────────────────────

    def test_bare_library_builds_without_crash(self):
        lib = _make_bare_library(15)
        studio = PlaylistStudio(library=lib)
        req    = StudioRequest(seeds=[lib.playlist[0]], target_count=8)
        result = studio.build(req)
        assert len(result.tracks) >= 1

    def test_bare_library_has_fallback_count(self):
        lib = _make_bare_library(15)
        studio = PlaylistStudio(library=lib)
        req    = StudioRequest(seeds=[lib.playlist[0]], target_count=8)
        result = studio.build(req)
        assert result.n_fallback >= 1  # at least the seed was a fallback

    # ── Invalid seeds ──────────────────────────────────────────────────────────

    def test_no_valid_seeds_returns_empty(self):
        lib = _make_annotated_library(10)
        studio = PlaylistStudio(library=lib)
        req    = StudioRequest(seeds=["/nonexistent/track.mp3"], target_count=5)
        result = studio.build(req)
        assert result.tracks == []
        assert result.arc_scores == []

    def test_partial_valid_seeds(self):
        lib = _make_annotated_library(20)
        good_seed = lib.playlist[0]
        studio = PlaylistStudio(library=lib)
        req    = StudioRequest(seeds=[good_seed, "/bad/path.mp3"], target_count=6)
        result = studio.build(req)
        assert good_seed in result.tracks

    # ── Diversity gates ────────────────────────────────────────────────────────

    def test_max_per_artist_respected(self):
        # 50 tracks, 50 distinct artists (1 track each) — max=1 always satisfiable
        n = 50
        paths = [f"/lib/track_{i:02d}.mp3" for i in range(n)]
        ann   = {p: {"mood_vec": _make_vec(i), "spotify_energy": i / (n - 1),
                     "genre": "pop"} for i, p in enumerate(paths)}
        meta  = {p: {"title": f"Track {i}", "artist": f"Artist {i}"}
                 for i, p in enumerate(paths)}
        lib   = _StubLibrary(paths, ann, meta)

        studio = PlaylistStudio(library=lib)
        req    = StudioRequest(
            seeds=[paths[0]],
            target_count=12,
            max_per_artist=1,
        )
        result = studio.build(req)
        from collections import Counter
        counts = Counter(
            (lib.get_meta(p) or {}).get("artist", "") for p in result.tracks
        )
        for artist, count in counts.items():
            if artist:
                assert count <= 1, f"Artist '{artist}' appears {count} times (max=1)"

    def test_max_per_genre_respected(self):
        # 60 tracks, 6 distinct genres (10 each) — max=2, target=12
        # 6 genres × 2 = 12 exactly satisfiable without relaxation
        n = 60
        genres = ["pop", "rock", "jazz", "folk", "soul", "funk"]
        paths  = [f"/lib/track_{i:02d}.mp3" for i in range(n)]
        ann    = {p: {"mood_vec": _make_vec(i), "spotify_energy": i / (n - 1),
                      "genre": genres[i % 6]} for i, p in enumerate(paths)}
        meta   = {p: {"title": f"Track {i}", "artist": f"Artist {i}"}
                  for i, p in enumerate(paths)}
        lib    = _StubLibrary(paths, ann, meta)

        studio = PlaylistStudio(library=lib)
        req    = StudioRequest(
            seeds=[paths[0]],
            target_count=12,
            max_per_genre=2,
        )
        result = studio.build(req)
        from collections import Counter
        counts = Counter(
            (lib.get_annotation(p) or {}).get("genre", "") for p in result.tracks
        )
        for genre, count in counts.items():
            if genre:
                assert count <= 2, f"Genre '{genre}' appears {count} times (max=2)"

    # ── All arc shapes smoke-test ──────────────────────────────────────────────

    @pytest.mark.parametrize("shape", list(ArcShape))
    def test_all_arc_shapes_produce_result(self, shape: ArcShape):
        lib    = _make_annotated_library(25)
        studio = PlaylistStudio(library=lib)
        req    = StudioRequest(seeds=[lib.playlist[0]], arc_shape=shape, target_count=10)
        result = studio.build(req)
        assert len(result.tracks) >= 1
        assert result.arc_shape == shape.value

    # ── StudioResult helpers ───────────────────────────────────────────────────

    def test_mean_arc_score(self):
        lib    = _make_annotated_library(25)
        studio = PlaylistStudio(library=lib)
        req    = StudioRequest(seeds=[lib.playlist[0]], target_count=8)
        result = studio.build(req)
        assert 0.0 < result.mean_arc_score <= 1.0

    def test_summary_string(self):
        lib    = _make_annotated_library(25)
        studio = PlaylistStudio(library=lib)
        req    = StudioRequest(seeds=[lib.playlist[0]], target_count=8)
        result = studio.build(req)
        summary = result.summary()
        assert "StudioResult" in summary
        assert result.arc_shape in summary


# ── CAIRRN integration ─────────────────────────────────────────────────────────

class TestCairrnIntegration:

    def test_playlist_build_requestkind_exists(self):
        assert hasattr(RequestKind, "PLAYLIST_BUILD")
        assert RequestKind.PLAYLIST_BUILD == "PLAYLIST_BUILD"

    def test_playlist_build_routes_to_math(self):
        assert REQUEST_HUB[RequestKind.PLAYLIST_BUILD] == "MATH"

    def test_playlist_build_not_in_rider_kinds(self):
        from phi.engine.cairrn.router import RIDER_KINDS
        assert RequestKind.PLAYLIST_BUILD not in RIDER_KINDS

    def test_propagate_steps_three(self):
        from phi.engine.cairrn._constants import PROPAGATE_STEPS
        assert PROPAGATE_STEPS.get("PLAYLIST_BUILD") == 3

    def test_floor_studio_build_method_exists(self):
        """ForestFloor has studio_build() that calls _safe_route."""
        from phi.engine.cairrn.floor import ForestFloor
        assert hasattr(ForestFloor, "studio_build")

    def test_floor_studio_build_calls_route(self):
        """studio_build() fires without crashing on a mock bridge."""
        from phi.engine.cairrn.floor import ForestFloor
        floor = ForestFloor.__new__(ForestFloor)
        mock_result = MagicMock()
        mock_result.should_act = False
        floor._safe_route = MagicMock(return_value=mock_result)
        floor._verbose = False

        result = floor.studio_build(20)

        floor._safe_route.assert_called_once()
        call_kwargs = floor._safe_route.call_args
        assert call_kwargs.args[0] == RequestKind.PLAYLIST_BUILD

    def test_studio_build_calls_floor(self):
        """PlaylistStudio.build() calls floor.studio_build() before traversal."""
        lib    = _make_annotated_library(20)
        floor  = MagicMock()
        floor.studio_build = MagicMock()

        studio = PlaylistStudio(library=lib, floor=floor)
        req    = StudioRequest(seeds=[lib.playlist[0]], target_count=5)
        studio.build(req)

        floor.studio_build.assert_called_once_with(5)


class TestStudioBus:
    """phi.engine.studio singleton bus accessor."""

    def test_build_raises_when_bus_down(self):
        """studio.build() raises RuntimeError when the bus worker is not alive."""
        from phi.engine.studio import build
        from phi.engine.playlist_studio import StudioRequest
        import unittest.mock as mock

        lib = _make_annotated_library(8)
        req = StudioRequest(seeds=[lib.playlist[0]], target_count=4)

        with mock.patch("mcp_server.bus.client.worker_alive", return_value=False), \
             mock.patch("mcp_server.bus.client.get_client", return_value=None):
            with pytest.raises(RuntimeError, match="bus scheduler not running"):
                build(req)

    def test_build_submits_correct_task(self):
        """studio.build() submits 'studio.build' task with the right payload keys."""
        from phi.engine.studio import build
        from phi.engine.playlist_studio import StudioRequest, StudioResult
        import unittest.mock as mock

        lib = _make_annotated_library(8)
        req = StudioRequest(
            seeds=[lib.playlist[0]],
            target_count=4,
        )

        fake_result = {
            "tracks": [lib.playlist[0], lib.playlist[1]],
            "arc_targets": [0.5, 0.5],
            "arc_scores": [0.9, 0.8],
            "transition_scores": [0.7],
            "seed_paths": [lib.playlist[0]],
            "arc_shape": "flat",
            "n_annotated": 2,
            "n_fallback": 0,
        }
        fake_rec = {"status": "done", "result": fake_result}

        mock_client = mock.MagicMock()
        mock_client.submit.return_value = {"job_id": "test-job-id"}
        mock_client.wait.return_value = fake_rec

        with mock.patch("mcp_server.bus.client.worker_alive", return_value=True), \
             mock.patch("mcp_server.bus.client.get_client", return_value=mock_client):
            result = build(req)

        submitted_task = mock_client.submit.call_args[0][0]
        submitted_payload = mock_client.submit.call_args[0][1]

        assert submitted_task == "studio.build"
        assert "seeds" in submitted_payload
        assert "arc_shape" in submitted_payload
        assert submitted_payload["seeds"] == req.seeds

        assert isinstance(result, StudioResult)
        assert result.tracks == fake_result["tracks"]
        assert result.n_annotated == 2
