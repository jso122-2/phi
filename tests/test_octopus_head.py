"""
Tests for OctopusAttentionHead and the regression pipeline.
"""
from __future__ import annotations

import math
import numpy as np
import pytest

from models import OctopusAttentionHead, FS_MAX_EXCLUSIVE
from models import (
    complement_graph,
    scup_cosine,
    angular_dist,
    complement_laplacian,
    tangent_flow,
    regression_matrix,
    compute_R,
)


# ===========================================================================
# OctopusAttentionHead
# ===========================================================================

class TestOctopusAttentionHeadFormula:
    def _small(self):
        """6-node example from pow.md."""
        A_bar = np.array([
            [0, 1, 1, 0, 1, 1],
            [1, 1, 0, 1, 1, 0],
            [1, 0, 1, 0, 1, 1],
            [0, 1, 0, 1, 0, 1],
            [0, 1, 1, 0, 1, 1],
            [1, 1, 0, 1, 1, 0],
        ], dtype=float)
        v = np.ones(6)
        d = np.ones(6)
        return A_bar, v, d

    def test_output_shape(self):
        head = OctopusAttentionHead(fs=0.0)
        A_bar, v, d = self._small()
        out = head.forward(A_bar, v, d)
        assert out.shape == (6, 6)

    def test_fs_subtracted(self):
        head_zero = OctopusAttentionHead(fs=0.0)
        head_two  = OctopusAttentionHead(fs=2.0)
        A_bar, v, d = self._small()
        diff = head_zero.forward(A_bar, v, d) - head_two.forward(A_bar, v, d)
        np.testing.assert_allclose(diff, np.full((6, 6), 2.0))

    def test_symmetric_when_Abar_is_symmetric(self):
        head = OctopusAttentionHead(fs=1.0)
        A_bar, v, d = self._small()
        out = head.forward(A_bar, v, d)
        np.testing.assert_allclose(out, out.T, atol=1e-10)

    def test_v_d_scaling(self):
        head = OctopusAttentionHead(fs=0.0)
        N = 4
        A_bar = np.ones((N, N), dtype=float)
        np.fill_diagonal(A_bar, 0.0)
        v = np.ones(N)
        d = 2.0 * np.ones(N)
        out2 = head.forward(A_bar, v, d)
        d_ones = np.ones(N)
        out1 = head.forward(A_bar, v, d_ones)
        np.testing.assert_allclose(out2, 2.0 * out1)

    def test_fs_ceiling_enforced_at_construction(self):
        head = OctopusAttentionHead(fs=999.0)
        assert head.fs < FS_MAX_EXCLUSIVE

    def test_set_fs_ceiling(self):
        head = OctopusAttentionHead()
        head.set_fs(999.0)
        assert head.fs < 24.0

    def test_zero_v_gives_negative_fs(self):
        head = OctopusAttentionHead(fs=5.0)
        N = 3
        A_bar = np.eye(N)
        v = np.zeros(N)
        d = np.ones(N)
        out = head.forward(A_bar, v, d)
        np.testing.assert_allclose(out, np.full((N, N), -5.0))

    def test_import_from_models_package(self):
        from models import OctopusAttentionHead as OAH
        assert OAH is OctopusAttentionHead


# ===========================================================================
# Regression pipeline
# ===========================================================================

class TestComplementGraph:
    def test_complement_of_complete_is_empty(self):
        N = 4
        A = np.ones((N, N)) - np.eye(N)
        A_bar = complement_graph(A)
        np.testing.assert_allclose(A_bar, np.zeros((N, N)))

    def test_complement_of_empty_is_complete_no_self_loops(self):
        N = 4
        A = np.zeros((N, N))
        A_bar = complement_graph(A)
        expected = np.ones((N, N)) - np.eye(N)
        np.testing.assert_allclose(A_bar, expected)

    def test_diagonal_always_zero(self):
        A = np.random.default_rng(0).random((5, 5))
        A_bar = complement_graph(A)
        np.testing.assert_allclose(np.diag(A_bar), np.zeros(5))


class TestScupCosine:
    def test_self_similarity_is_one_over_tau(self):
        H = np.eye(4)
        tau = 2.0
        C = scup_cosine(H, tau)
        np.testing.assert_allclose(np.diag(C), np.full(4, 1.0 / tau), atol=1e-10)

    def test_orthogonal_vectors_give_zero(self):
        H = np.eye(4)
        tau = 1.0
        C = scup_cosine(H, tau)
        off_diag = C - np.diag(np.diag(C))
        np.testing.assert_allclose(off_diag, 0.0, atol=1e-10)

    def test_tau_scales_output(self):
        H = np.random.default_rng(1).standard_normal((3, 8))
        C1 = scup_cosine(H, 1.0)
        C2 = scup_cosine(H, 2.0)
        np.testing.assert_allclose(C1, 2.0 * C2, atol=1e-10)


class TestAngularDist:
    def test_range_zero_to_pi(self):
        C = np.array([[1.0, 0.0, -1.0], [0.0, 1.0, 0.5], [-1.0, 0.5, 1.0]])
        Theta = angular_dist(C)
        assert Theta.min() >= 0.0
        assert Theta.max() <= math.pi + 1e-10

    def test_acos_1_is_0(self):
        C = np.ones((3, 3))
        Theta = angular_dist(C)
        np.testing.assert_allclose(Theta, 0.0, atol=1e-10)

    def test_acos_minus1_is_pi(self):
        C = -np.ones((2, 2))
        Theta = angular_dist(C)
        np.testing.assert_allclose(Theta, math.pi, atol=1e-10)


class TestComplementLaplacian:
    def test_row_sum_is_zero(self):
        N = 5
        A = np.zeros((N, N))
        A_bar = complement_graph(A)
        L_bar = complement_laplacian(A_bar)
        row_sums = L_bar.sum(axis=1)
        np.testing.assert_allclose(row_sums, 0.0, atol=1e-10)

    def test_diagonal_equals_complement_degree(self):
        A = np.zeros((4, 4))
        A_bar = complement_graph(A)
        L_bar = complement_laplacian(A_bar)
        # empty G → complete G̅ (no self-loops), each node has degree 3
        np.testing.assert_allclose(np.diag(L_bar), np.full(4, 3.0))


class TestComputeR:
    def test_R_shape(self):
        N, d = 5, 16
        A = np.zeros((N, N))
        H = np.random.default_rng(2).standard_normal((N, d))
        R, A_bar, Theta, F = compute_R(A, H, tau=1.0)
        assert R.shape == (N, d)

    def test_pipeline_deterministic(self):
        N, d = 4, 8
        A = np.eye(N) * 0
        H = np.random.default_rng(99).standard_normal((N, d))
        R1, *_ = compute_R(A, H, tau=1.5)
        R2, *_ = compute_R(A, H, tau=1.5)
        np.testing.assert_array_equal(R1, R2)
