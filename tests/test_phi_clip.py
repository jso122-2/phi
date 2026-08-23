"""
tests/test_phi_clip_tool.py

Direct-import tests for the gemini_clip MCP tool.

Strategy: monkeypatch mcp_server.tools.phi_clip._get_session so that tests
never touch the real library on disk.  The gate is bypassed by calling the
inner function directly (the @requires_init decorator returns early when the
gate is closed, so we open it before the tests that need it).
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest

# Open the session gate before importing the tool so @requires_init passes.
from mcp_server._gate import open_gate

open_gate()

from mcp_server.tools.phi_clip import gemini_clip, is_warmed  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers — synthetic Track / session / clipper
# ---------------------------------------------------------------------------

def _make_track(name: str, artist: str, tags: list[str]) -> Any:
    from phi._track import Track
    t = Track(path=Path(f"/{name}.mp3"), json_path=Path(f"/{name}.json"))
    t.name = name
    t.artist = artist
    t.lfm_tags = tags
    return t


def _make_synthetic_session(n_tracks: int = 4):
    """Return a minimal fake PhiTracerSession-like object."""
    tracks = [
        _make_track("Track A", "Artist 1", ["techno", "dark", "ambient"]),
        _make_track("Track B", "Artist 2", ["piano", "sad", "classical"]),
        _make_track("Track C", "Artist 3", ["jazz", "swing", "bebop"]),
        _make_track("Track D", "Artist 4", ["pop", "indie"]),
    ][:n_tracks]

    H = np.random.default_rng(42).standard_normal((n_tracks, 256)).astype(np.float32)
    norms = np.linalg.norm(H, axis=1, keepdims=True)
    H = H / np.where(norms == 0, 1.0, norms)

    A = np.zeros((n_tracks, n_tracks), dtype=np.float32)

    snap = SimpleNamespace(tracks=tracks, H=H, A=A, N=n_tracks)

    from phi.models.clap_proj import CLAPProjection, MetadataEncoder
    proj = CLAPProjection(rng=np.random.default_rng(0))
    enc = MetadataEncoder()
    all_tags = [tag for t in tracks for tag in t.lfm_tags]
    enc.set_vocab(list(dict.fromkeys(all_tags)))

    phi_graph = SimpleNamespace(_proj=proj, _encoder=enc)

    session = SimpleNamespace(
        phi_graph=phi_graph,
        snapshot=snap,
    )
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGeminiClipLibraryUnavailable:
    """When _get_session returns None the tool should degrade gracefully."""

    def test_library_available_false(self, monkeypatch):
        monkeypatch.setattr("mcp_server.tools.phi_clip._get_session", lambda: None)
        result = gemini_clip(query="dark techno")
        assert result["library_available"] is False

    def test_empty_tracks(self, monkeypatch):
        monkeypatch.setattr("mcp_server.tools.phi_clip._get_session", lambda: None)
        result = gemini_clip(query="dark techno")
        assert result["tracks"] == []

    def test_query_echoed(self, monkeypatch):
        monkeypatch.setattr("mcp_server.tools.phi_clip._get_session", lambda: None)
        result = gemini_clip(query="piano in C minor")
        assert result["query"] == "piano in C minor"

    def test_n_tracks_searched_zero(self, monkeypatch):
        monkeypatch.setattr("mcp_server.tools.phi_clip._get_session", lambda: None)
        result = gemini_clip(query="anything")
        assert result["n_tracks_searched"] == 0

    def test_blend_in_result(self, monkeypatch):
        monkeypatch.setattr("mcp_server.tools.phi_clip._get_session", lambda: None)
        result = gemini_clip(query="techno", blend=0.3)
        assert result["blend"] == pytest.approx(0.3)


class TestGeminiClipWithSession:
    """When a synthetic session is available the tool must return valid data."""

    @pytest.fixture(autouse=True)
    def _patch_session(self, monkeypatch):
        session = _make_synthetic_session(n_tracks=4)
        monkeypatch.setattr("mcp_server.tools.phi_clip._session", None)
        monkeypatch.setattr("mcp_server.tools.phi_clip._get_session", lambda: session)

    def test_library_available_true(self):
        result = gemini_clip(query="dark techno")
        assert result["library_available"] is True

    def test_query_echoed(self):
        result = gemini_clip(query="sad piano")
        assert result["query"] == "sad piano"

    def test_blend_stored(self):
        result = gemini_clip(query="ambient", blend=0.7)
        assert result["blend"] == pytest.approx(0.7)

    def test_tracks_length_respects_top_k(self):
        result = gemini_clip(query="jazz", top_k=2)
        assert len(result["tracks"]) <= 2

    def test_tracks_length_default_top_k(self):
        result = gemini_clip(query="techno")
        # 4 tracks in synthetic library; default top_k=5 → at most 4 returned
        assert len(result["tracks"]) <= 5
        assert len(result["tracks"]) > 0

    def test_track_keys_present(self):
        result = gemini_clip(query="ambient")
        track = result["tracks"][0]
        for key in ("rank", "name", "artist", "tags", "semantic_score", "h_space_score", "p_sps"):
            assert key in track, f"Missing key: {key}"

    def test_track_name_and_artist_are_strings(self):
        result = gemini_clip(query="techno")
        for track in result["tracks"]:
            assert isinstance(track["name"], str)
            assert isinstance(track["artist"], str)

    def test_track_tags_is_list(self):
        result = gemini_clip(query="jazz")
        for track in result["tracks"]:
            assert isinstance(track["tags"], list)

    def test_p_sps_in_range(self):
        result = gemini_clip(query="dark ambient")
        for track in result["tracks"]:
            assert 0.0 <= track["p_sps"] <= 1.0

    def test_ranks_are_zero_based_sequential(self):
        result = gemini_clip(query="piano")
        ranks = [t["rank"] for t in result["tracks"]]
        assert ranks == list(range(len(ranks)))

    def test_context_string_non_empty(self):
        result = gemini_clip(query="techno")
        assert isinstance(result["context"], str)
        assert len(result["context"]) > 0

    def test_n_tracks_searched_matches_library(self):
        result = gemini_clip(query="anything")
        # synthetic session has 4 tracks
        assert result["n_tracks_searched"] == 4

    def test_blend_zero_allowed(self):
        # blend=0.0 must not be blocked by param_bounds_guard (alpha is the gated name)
        result = gemini_clip(query="techno", blend=0.0)
        assert result["library_available"] is True
        assert result["blend"] == pytest.approx(0.0)

    def test_blend_one_allowed(self):
        result = gemini_clip(query="techno", blend=1.0)
        assert result["library_available"] is True
        assert result["blend"] == pytest.approx(1.0)


class TestIsWarmed:
    def test_false_when_session_none(self, monkeypatch):
        import mcp_server.tools.phi_clip as phi_clip_mod
        monkeypatch.setattr(phi_clip_mod, "_session", None)
        assert is_warmed() is False

    def test_true_when_session_set(self, monkeypatch):
        import mcp_server.tools.phi_clip as phi_clip_mod
        monkeypatch.setattr(phi_clip_mod, "_session", object())
        assert is_warmed() is True
