"""tests/test_window_pipeline.py — smoke tests for phi.graph._window_pipeline."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from phi._track import Track
from phi.graph._window_pipeline import (
    WindowTensors,
    WindowResult,
    build_window_tensors,
    run_window,
    _complement,
    _audio_adjacency,
)
from phi.metadata.schema import AudioFeatures, GraphPosition, SongNode, _SHARD_MAP
from models.ssm import SSMCore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_track(i: int, tags: list[str] | None = None) -> Track:
    return Track(
        path=Path(f"/fake/{i}.mp3"),
        json_path=Path(f"/fake/{i}.json"),
        name=f"Track {i}",
        artist="Artist",
        lfm_tags=tags if tags is not None else ["soul" if i % 2 == 0 else "jazz"],
    )


def _make_node(
    node_id: int,
    tags: list[str] | None = None,
    h_u: list[float] | None = None,
    audio: AudioFeatures | None = None,
) -> SongNode:
    h = h_u if h_u is not None else list(np.random.default_rng(node_id).standard_normal(256))
    return SongNode(
        track=_make_track(node_id, tags),
        audio=audio if audio is not None else AudioFeatures(),
        position=GraphPosition(node_id=node_id, shard=_SHARD_MAP[node_id], h_u=h),
    )


def _six_nodes(shared_tag: bool = False) -> list[SongNode]:
    if shared_tag:
        return [_make_node(i, tags=["soul"]) for i in range(6)]
    return [_make_node(i) for i in range(6)]


# ---------------------------------------------------------------------------
# _complement
# ---------------------------------------------------------------------------

class TestComplement:
    def test_empty_graph_gives_complete_complement(self):
        A = np.zeros((4, 4))
        A_bar = _complement(A)
        expected = np.ones((4, 4)) - np.eye(4)
        np.testing.assert_allclose(A_bar, expected)

    def test_complete_graph_gives_empty_complement(self):
        A = np.ones((4, 4)) - np.eye(4)
        A_bar = _complement(A)
        np.testing.assert_allclose(A_bar, np.zeros((4, 4)))

    def test_diagonal_always_zero(self):
        A = np.zeros((5, 5))
        A_bar = _complement(A)
        np.testing.assert_allclose(np.diag(A_bar), np.zeros(5))

    def test_symmetric_input_symmetric_output(self):
        A = np.array([[0,1,0],[1,0,1],[0,1,0]], dtype=float)
        A_bar = _complement(A)
        np.testing.assert_allclose(A_bar, A_bar.T)


# ---------------------------------------------------------------------------
# _audio_adjacency
# ---------------------------------------------------------------------------

class TestAudioAdjacency:
    def test_shape(self):
        nodes = _six_nodes()
        A = _audio_adjacency(nodes, threshold=0.0)
        assert A.shape == (6, 6)

    def test_diagonal_zero(self):
        nodes = _six_nodes()
        A = _audio_adjacency(nodes, threshold=0.0)
        np.testing.assert_allclose(np.diag(A), np.zeros(6))

    def test_identical_audio_connected_at_low_threshold(self):
        af = AudioFeatures(tempo=120.0)
        nodes = [_make_node(i, audio=af) for i in range(3)]
        A = _audio_adjacency(nodes, threshold=0.0)
        # All same vector (non-zero) → cosine = 1.0 → all connected (except diagonal)
        expected = np.ones((3, 3)) - np.eye(3)
        np.testing.assert_allclose(A, expected)

    def test_zero_audio_no_edge(self):
        nodes = _six_nodes()  # all zeroed AudioFeatures
        A = _audio_adjacency(nodes, threshold=0.5)
        np.testing.assert_allclose(A, np.zeros((6, 6)))


# ---------------------------------------------------------------------------
# build_window_tensors
# ---------------------------------------------------------------------------

class TestBuildWindowTensors:
    def test_A_shape(self):
        nodes = _six_nodes()
        t = build_window_tensors(nodes)
        assert t.A.shape == (6, 6)

    def test_A_bar_shape(self):
        nodes = _six_nodes()
        t = build_window_tensors(nodes)
        assert t.A_bar.shape == (6, 6)

    def test_H_phi_shape(self):
        nodes = _six_nodes()
        t = build_window_tensors(nodes)
        assert t.H_phi.shape == (6, 256)

    def test_A_bar_is_complement_of_A(self):
        nodes = _six_nodes()
        t = build_window_tensors(nodes)
        expected_bar = _complement(t.A)
        np.testing.assert_allclose(t.A_bar, expected_bar)

    def test_H_phi_matches_h_u(self):
        nodes = _six_nodes()
        t = build_window_tensors(nodes)
        for i, node in enumerate(nodes):
            np.testing.assert_allclose(t.H_phi[i], node.position.h_u)

    def test_shared_tags_produce_edges(self):
        nodes = _six_nodes(shared_tag=True)  # all "soul"
        t = build_window_tensors(nodes, tag_threshold=0.0)
        # All same tag → all connected
        assert t.A.sum() > 0

    def test_disjoint_tags_no_edges(self):
        # Each node has a unique tag → Jaccard = 0 for all pairs
        nodes = [_make_node(i, tags=[f"unique_tag_{i}"]) for i in range(6)]
        t = build_window_tensors(nodes, tag_threshold=0.0)
        assert t.A.sum() == 0.0

    def test_A_diagonal_zero(self):
        nodes = _six_nodes(shared_tag=True)
        t = build_window_tensors(nodes)
        np.testing.assert_allclose(np.diag(t.A), np.zeros(6))

    def test_A_bar_diagonal_zero(self):
        nodes = _six_nodes()
        t = build_window_tensors(nodes)
        np.testing.assert_allclose(np.diag(t.A_bar), np.zeros(6))

    def test_empty_nodes_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            build_window_tensors([])

    def test_N_property(self):
        nodes = _six_nodes()
        t = build_window_tensors(nodes)
        assert t.N == 6

    def test_partial_window(self):
        nodes = [_make_node(i) for i in range(3)]
        t = build_window_tensors(nodes)
        assert t.A.shape == (3, 3)
        assert t.H_phi.shape == (3, 256)


# ---------------------------------------------------------------------------
# run_window
# ---------------------------------------------------------------------------

class TestRunWindow:
    def test_R_shape(self):
        nodes = _six_nodes()
        ssm = SSMCore(d=256, n_layers=2, rng=np.random.default_rng(0))
        result = run_window(nodes, ssm)
        assert result.R.shape == (6, 256)

    def test_A_bar_shape(self):
        nodes = _six_nodes()
        ssm = SSMCore(d=256, n_layers=2, rng=np.random.default_rng(0))
        result = run_window(nodes, ssm)
        assert result.A_bar.shape == (6, 6)

    def test_tau_positive(self):
        nodes = _six_nodes()
        ssm = SSMCore(d=256, n_layers=2, rng=np.random.default_rng(0))
        result = run_window(nodes, ssm)
        assert result.tau > 0.0

    def test_H_ssm_shape(self):
        nodes = _six_nodes()
        ssm = SSMCore(d=256, n_layers=2, rng=np.random.default_rng(0))
        result = run_window(nodes, ssm)
        assert result.H_ssm.shape == (6, 256)

    def test_deterministic_same_ssm_state(self):
        nodes = _six_nodes()
        ssm = SSMCore(d=256, n_layers=2, rng=np.random.default_rng(42))
        r1 = run_window(nodes, ssm)
        ssm2 = SSMCore(d=256, n_layers=2, rng=np.random.default_rng(42))
        r2 = run_window(nodes, ssm2)
        np.testing.assert_allclose(r1.R, r2.R, atol=1e-10)

    def test_Theta_range_zero_to_pi(self):
        nodes = _six_nodes()
        ssm = SSMCore(d=256, n_layers=2, rng=np.random.default_rng(0))
        result = run_window(nodes, ssm)
        assert result.Theta.min() >= 0.0 - 1e-10
        assert result.Theta.max() <= math.pi + 1e-10
