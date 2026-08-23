"""Tests for phi.models.coplay_rank (CoPlayRanker).

Covers:
- fit: returns {} for fewer than 3 played tracks
- fit: hub tracks (played often with others) rank higher than isolated tracks
- fit: scores are in [COPLAY_FLOOR, 1.0]
- fit: unplayed tracks absent from result → _phi_rank fallback applies
- annotate: writes phi_rank, respects overwrite=False
- save / load round-trip
- maybe_rank_and_annotate: idempotent, writes annotations
- PageRank ordering: track played in many sessions > track played once
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from phi.models.coplay_rank import (
    CoPlayRanker,
    COPLAY_FLOOR,
    _build_adjacency,
    _pagerank,
    maybe_rank_and_annotate,
    refetch_coplay,
)
import numpy as np


# ── helpers ────────────────────────────────────────────────────────────────────

def _ts(offset_secs: int = 0) -> str:
    """ISO timestamp offset from a fixed base."""
    base = datetime(2026, 1, 1, 12, 0, 0)
    return (base + timedelta(seconds=offset_secs)).isoformat()


def _make_library(tracks: list[dict]) -> MagicMock:
    """Stub library.

    Each dict: {"path", "last_played" (secs offset), "completion_rate", "plays"}
    """
    lib = MagicMock()
    lib.playlist = [t["path"] for t in tracks]
    lib.meta_cache = {t["path"]: {} for t in tracks}
    lib.annotations = {}
    lib.play_stats = {}
    for t in tracks:
        if t.get("last_played") is not None:
            lib.play_stats[t["path"]] = {
                "last_played": _ts(t["last_played"]),
                "completion_rate": t.get("completion_rate", 0.8),
                "plays": t.get("plays", 1),
            }
    return lib


# ── _build_adjacency ───────────────────────────────────────────────────────────

class TestBuildAdjacency:
    def test_symmetric(self):
        played = [("/a", _ts(0), 0.8), ("/b", _ts(10), 0.9), ("/c", _ts(20), 0.7)]
        paths, A = _build_adjacency(played, window=3)
        np.testing.assert_allclose(A, A.T, atol=1e-6)

    def test_no_self_edges(self):
        played = [("/a", _ts(0), 0.8), ("/b", _ts(10), 0.9)]
        _, A = _build_adjacency(played, window=3)
        assert A.diagonal().sum() == 0.0

    def test_outside_window_no_edge(self):
        played = [("/a", _ts(0), 0.8), ("/b", _ts(10), 0.9), ("/c", _ts(20), 0.7)]
        # window=1 → only adjacent tracks get edges
        _, A = _build_adjacency(played, window=1)
        # A[0,2] and A[2,0] should be 0 (2 apart)
        assert A[0, 2] == 0.0

    def test_weights_positive(self):
        played = [
            ("/a", _ts(0), 0.8),
            ("/b", _ts(10), 0.9),
            ("/c", _ts(20), 0.5),
        ]
        _, A = _build_adjacency(played, window=2)
        assert A.sum() > 0.0

    def test_caps_at_max_played(self):
        # Build 3000 tracks — should be capped to 2000
        played = [(f"/{i}", _ts(i * 10), 0.8) for i in range(3000)]
        paths, A = _build_adjacency(played, window=8)
        assert len(paths) == 2000
        assert A.shape == (2000, 2000)


# ── _pagerank ──────────────────────────────────────────────────────────────────

class TestPageRank:
    def test_sums_to_one(self):
        A = np.array([[0, 1, 1], [1, 0, 1], [1, 1, 0]], dtype=np.float32)
        r = _pagerank(A, damping=0.85, iterations=50)
        assert abs(r.sum() - 1.0) < 1e-5

    def test_uniform_graph_uniform_rank(self):
        # Regular graph → all nodes equal rank
        A = np.array([[0, 1, 1], [1, 0, 1], [1, 1, 0]], dtype=np.float32)
        r = _pagerank(A, damping=0.85, iterations=50)
        assert np.std(r) < 0.01

    def test_hub_node_ranks_higher(self):
        # Node 0 connected to all; nodes 1,2 only connected to 0
        A = np.array([
            [0, 1, 1, 1],
            [1, 0, 0, 0],
            [1, 0, 0, 0],
            [1, 0, 0, 0],
        ], dtype=np.float32)
        r = _pagerank(A, damping=0.85, iterations=50)
        assert r[0] > r[1]

    def test_dangling_node_handled(self):
        # Node 2 has no outgoing edges (zero column)
        A = np.array([[0, 1, 0], [1, 0, 0], [0, 0, 0]], dtype=np.float32)
        r = _pagerank(A, damping=0.85, iterations=50)
        assert abs(r.sum() - 1.0) < 1e-4


# ── CoPlayRanker.fit ───────────────────────────────────────────────────────────

class TestCoPlayRankerFit:
    def test_returns_empty_for_fewer_than_3(self):
        lib = _make_library([
            {"path": "/a", "last_played": 0},
            {"path": "/b", "last_played": 10},
        ])
        scores = CoPlayRanker().fit(lib)
        assert scores == {}

    def test_returns_empty_for_no_played(self):
        lib = _make_library([
            {"path": "/a"},   # no last_played
        ])
        scores = CoPlayRanker().fit(lib)
        assert scores == {}

    def test_scores_in_valid_range(self):
        lib = _make_library([
            {"path": f"/{i}", "last_played": i * 60, "completion_rate": 0.9}
            for i in range(10)
        ])
        scores = CoPlayRanker().fit(lib)
        assert scores
        for path, score in scores.items():
            assert COPLAY_FLOOR <= score <= 1.0 + 1e-6, f"{path}: {score} out of range"

    def test_unplayed_tracks_absent(self):
        lib = _make_library([
            {"path": "/a", "last_played": 0},
            {"path": "/b", "last_played": 60},
            {"path": "/c", "last_played": 120},
            {"path": "/d"},   # never played
        ])
        scores = CoPlayRanker().fit(lib)
        assert "/d" not in scores

    def test_hub_track_ranks_higher_than_isolated(self):
        """Track played every session should rank above one played once alone."""
        # Hub: /hub is always within window of other tracks
        # Isolated: /iso is played once, far from any other track (window gap)
        tracks = []
        # 5 sessions of 3 tracks each, hub always present at position 0
        t = 0
        for s in range(5):
            tracks.append({"path": "/hub", "last_played": t, "completion_rate": 0.9})
            tracks.append({"path": f"/companion_{s}", "last_played": t + 30, "completion_rate": 0.8})
            tracks.append({"path": f"/companion_{s}b", "last_played": t + 60, "completion_rate": 0.8})
            t += 3600   # 1 hour between sessions

        # Isolated: played once, 10 hours after last session (outside window in history)
        # Actually the window is positional, not temporal — so isolation means
        # appearing far apart in the sorted-by-time list.
        # Add many intermediary tracks so /iso is positionally far from everything
        for i in range(20):
            tracks.append({"path": f"/gap_{i}", "last_played": t + i * 30, "completion_rate": 0.5})
        t += 20 * 30
        tracks.append({"path": "/iso", "last_played": t + 5000, "completion_rate": 0.9})

        lib = _make_library(tracks)
        scores = CoPlayRanker(window=3).fit(lib)
        hub_score = scores.get("/hub", 0.5)
        iso_score = scores.get("/iso", 0.5)
        assert hub_score > iso_score, (
            f"hub_score={hub_score:.3f} should exceed iso_score={iso_score:.3f}"
        )

    def test_high_completion_edges_stronger(self):
        """Two tracks always completed together should both rank higher than
        two tracks paired but with low completion rates."""
        # High-completion pair: /a and /b, alternating, completion=0.95
        # Low-completion pair: /c and /d, alternating, completion=0.1
        tracks = []
        for i in range(6):
            tracks.append({"path": "/a", "last_played": i * 60, "completion_rate": 0.95})
            tracks.append({"path": "/b", "last_played": i * 60 + 30, "completion_rate": 0.95})
        for i in range(6):
            tracks.append({"path": "/c", "last_played": 400 + i * 60, "completion_rate": 0.1})
            tracks.append({"path": "/d", "last_played": 400 + i * 60 + 30, "completion_rate": 0.1})
        lib = _make_library(tracks)
        scores = CoPlayRanker().fit(lib)
        mean_high = (scores.get("/a", 0.5) + scores.get("/b", 0.5)) / 2.0
        mean_low  = (scores.get("/c", 0.5) + scores.get("/d", 0.5)) / 2.0
        assert mean_high > mean_low, (
            f"high-completion pair ({mean_high:.3f}) should outrank low-completion ({mean_low:.3f})"
        )


# ── annotate ──────────────────────────────────────────────────────────────────

class TestAnnotate:
    def test_writes_phi_rank(self):
        lib = _make_library([
            {"path": "/a", "last_played": 0},
            {"path": "/b", "last_played": 60},
            {"path": "/c", "last_played": 120},
        ])
        scores = {"/a": 0.8, "/b": 0.5, "/c": 0.3}
        CoPlayRanker.annotate(lib, scores)
        assert lib.annotations.get("/a", {}).get("phi_rank") == 0.8

    def test_does_not_overwrite_by_default(self):
        lib = _make_library([{"path": "/a", "last_played": 0}])
        lib.annotations = {"/a": {"phi_rank": 0.99}}
        CoPlayRanker.annotate(lib, {"/a": 0.1}, overwrite=False)
        assert lib.annotations["/a"]["phi_rank"] == 0.99

    def test_overwrite_replaces(self):
        lib = _make_library([{"path": "/a", "last_played": 0}])
        lib.annotations = {"/a": {"phi_rank": 0.99}}
        CoPlayRanker.annotate(lib, {"/a": 0.1}, overwrite=True)
        assert lib.annotations["/a"]["phi_rank"] == 0.1

    def test_returns_count(self):
        lib = _make_library([])
        lib.annotations = {}
        n = CoPlayRanker.annotate(lib, {"/a": 0.7, "/b": 0.4})
        assert n == 2


# ── persistence ───────────────────────────────────────────────────────────────

class TestPersistence:
    def test_save_load_roundtrip(self, tmp_path):
        scores = {"/a": 0.9, "/b": 0.4, "/c": 0.6}
        ckpt = tmp_path / "coplay.json"
        CoPlayRanker.save(scores, ckpt)
        loaded = CoPlayRanker.load(ckpt)
        assert loaded == scores

    def test_load_returns_none_when_absent(self, tmp_path):
        result = CoPlayRanker.load(tmp_path / "nonexistent.json")
        assert result is None

    def test_load_returns_none_on_corrupt(self, tmp_path):
        ckpt = tmp_path / "bad.json"
        ckpt.write_text("not json", encoding="utf-8")
        assert CoPlayRanker.load(ckpt) is None


# ── maybe_rank_and_annotate ───────────────────────────────────────────────────

class TestMaybeRankAndAnnotate:
    def setup_method(self):
        refetch_coplay()   # reset singleton before each test

    def test_returns_true_on_success(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PHI_COPLAY_RANK", str(tmp_path / "rank.json"))
        lib = _make_library([
            {"path": f"/{i}", "last_played": i * 60, "completion_rate": 0.8}
            for i in range(5)
        ])
        result = maybe_rank_and_annotate(lib)
        assert result is True

    def test_idempotent(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PHI_COPLAY_RANK", str(tmp_path / "rank.json"))
        lib = _make_library([
            {"path": f"/{i}", "last_played": i * 60}
            for i in range(5)
        ])
        assert maybe_rank_and_annotate(lib) is True
        # Second call is a no-op (singleton already set)
        assert maybe_rank_and_annotate(lib) is True

    def test_writes_phi_rank_to_annotations(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PHI_COPLAY_RANK", str(tmp_path / "rank.json"))
        lib = _make_library([
            {"path": f"/{i}", "last_played": i * 60, "completion_rate": 0.85}
            for i in range(6)
        ])
        maybe_rank_and_annotate(lib)
        # At least some annotations should have phi_rank
        annotated = [
            p for p in lib.playlist
            if lib.annotations.get(p, {}).get("phi_rank") is not None
        ]
        assert len(annotated) > 0


# ── _phi_rank fallback wiring ─────────────────────────────────────────────────

class TestPhiRankFallback:
    """_scoring._phi_rank reads phi_rank from annotations; test it reads correctly."""

    def test_phi_rank_reads_annotation(self):
        from phi.core.ranker._scoring import _phi_rank
        assert _phi_rank({"phi_rank": 0.75}) == pytest.approx(0.75)

    def test_phi_rank_defaults_to_half(self):
        from phi.core.ranker._scoring import _phi_rank
        assert _phi_rank({}) == pytest.approx(0.5)

    def test_phi_rank_clamps(self):
        from phi.core.ranker._scoring import _phi_rank
        assert _phi_rank({"phi_rank": 1.5}) == pytest.approx(1.0)
        assert _phi_rank({"phi_rank": -0.5}) == pytest.approx(0.0)
