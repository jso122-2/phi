"""tests/test_metadata_schema.py — smoke tests for phi.metadata schema layer."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from phi._track import Track
from phi.metadata.schema import (
    AudioFeatures,
    GraphPosition,
    SongNode,
    WINDOW_SIZE,
    _SHARD_MAP,
)
from phi.metadata.node_builder import build_window, update_degrees


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_track(i: int) -> Track:
    return Track(
        path=Path(f"/fake/{i}.mp3"),
        json_path=Path(f"/fake/{i}.json"),
        name=f"Track {i}",
        artist="Test Artist",
    )


# ---------------------------------------------------------------------------
# AudioFeatures
# ---------------------------------------------------------------------------

class TestAudioFeatures:
    def test_defaults_are_zero(self):
        af = AudioFeatures()
        assert af.tempo == 0.0
        assert len(af.chroma_mean) == 12
        assert len(af.mfcc_mean) == 13

    def test_to_vector_shape(self):
        af = AudioFeatures()
        v = af.to_vector()
        assert v.shape == (30,)
        assert v.dtype == np.float64

    def test_to_vector_values(self):
        af = AudioFeatures(tempo=120.0, loudness_db=-20.0)
        v = af.to_vector()
        assert v[0] == pytest.approx(120.0)
        assert v[1] == pytest.approx(-20.0)

    def test_bad_chroma_length_raises(self):
        with pytest.raises(ValueError, match="chroma_mean"):
            AudioFeatures(chroma_mean=[0.0] * 11)

    def test_bad_mfcc_length_raises(self):
        with pytest.raises(ValueError, match="mfcc_mean"):
            AudioFeatures(mfcc_mean=[0.0] * 5)


# ---------------------------------------------------------------------------
# GraphPosition
# ---------------------------------------------------------------------------

class TestGraphPosition:
    def test_defaults(self):
        gp = GraphPosition()
        assert gp.node_id == 0
        assert gp.degree == 0
        assert gp.shard == 0
        assert len(gp.h_u) == 256

    def test_invalid_node_id_raises(self):
        with pytest.raises(ValueError, match="node_id"):
            GraphPosition(node_id=6)

    def test_invalid_shard_raises(self):
        with pytest.raises(ValueError, match="shard"):
            GraphPosition(shard=8)

    def test_invalid_h_u_length_raises(self):
        with pytest.raises(ValueError, match="h_u"):
            GraphPosition(h_u=[0.0] * 10)


# ---------------------------------------------------------------------------
# SongNode
# ---------------------------------------------------------------------------

class TestSongNode:
    def test_node_id_property(self):
        track = _fake_track(0)
        node = SongNode(
            track=track,
            audio=AudioFeatures(),
            position=GraphPosition(node_id=3, shard=_SHARD_MAP[3]),
        )
        assert node.node_id == 3

    def test_display(self):
        track = _fake_track(0)
        node = SongNode(
            track=track,
            audio=AudioFeatures(),
            position=GraphPosition(node_id=0, shard=_SHARD_MAP[0]),
        )
        assert "Track 0" in node.display


# ---------------------------------------------------------------------------
# build_window
# ---------------------------------------------------------------------------

class TestBuildWindow:
    def test_builds_six_nodes(self):
        tracks = [_fake_track(i) for i in range(6)]
        nodes = build_window(tracks, extract_audio=False)
        assert len(nodes) == 6

    def test_node_ids_sequential(self):
        tracks = [_fake_track(i) for i in range(6)]
        nodes = build_window(tracks, extract_audio=False)
        assert [n.node_id for n in nodes] == list(range(6))

    def test_shard_map_applied(self):
        tracks = [_fake_track(i) for i in range(6)]
        nodes = build_window(tracks, extract_audio=False)
        for node in nodes:
            assert node.shard == _SHARD_MAP[node.node_id]

    def test_window_size_exceeded_raises(self):
        tracks = [_fake_track(i) for i in range(WINDOW_SIZE + 1)]
        with pytest.raises(ValueError, match="Window size"):
            build_window(tracks, extract_audio=False)

    def test_partial_window_allowed(self):
        tracks = [_fake_track(i) for i in range(3)]
        nodes = build_window(tracks, extract_audio=False)
        assert len(nodes) == 3

    def test_update_degrees(self):
        tracks = [_fake_track(i) for i in range(3)]
        nodes = build_window(tracks, extract_audio=False)
        A = np.array([
            [0, 1, 0],
            [1, 0, 1],
            [0, 1, 0],
        ], dtype=np.float64)
        update_degrees(nodes, A)
        assert nodes[0].position.degree == 1
        assert nodes[1].position.degree == 2
        assert nodes[2].position.degree == 1
