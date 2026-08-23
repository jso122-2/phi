"""
Tests for models.bert_clipper.BERTClipper.

Coverage:
  - encode() output shapes and types
  - tau is strictly positive
  - lora_proj shape matches (d, lora_rank)
  - lora_proj is a slice of last layer's W_O
  - encode() is deterministic for the same input
  - different inputs produce different H
  - update() returns a float loss
  - update() changes W_emb and W_out
  - update() gradient clipping: large gradient norm is clamped
  - n_params > 0
  - import from models package
  - d_in != d (non-square embedding)
  - TracerDaemon.bert + lora_proj properties live after first run_once()
"""
from __future__ import annotations

import math
import numpy as np
import pytest

from models.bert_clipper import BERTClipper
from models import BERTClipper as BERTClipperFromPackage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_clipper(d: int = 16, lora_rank: int = 4) -> BERTClipper:
    """Small BERTClipper for fast tests (d=16 so d_head=4 with n_heads=4)."""
    return BERTClipper(d_in=d, d=d, n_layers=2, n_heads=4, lora_rank=lora_rank, rng=np.random.default_rng(0))


def random_X(N: int = 6, d: int = 16) -> np.ndarray:
    return np.random.default_rng(42).standard_normal((N, d)).astype(np.float64)


# ===========================================================================
# encode() output shapes
# ===========================================================================

class TestEncodeShapes:
    def test_H_shape(self):
        bc = make_clipper(d=16)
        X = random_X(N=5, d=16)
        H, tau, lora_proj = bc.encode(X)
        assert H.shape == (5, 16)

    def test_tau_is_positive_float(self):
        bc = make_clipper()
        _, tau, _ = bc.encode(random_X())
        assert isinstance(tau, float)
        assert tau > 0.0

    def test_lora_proj_shape(self):
        bc = make_clipper(d=16, lora_rank=4)
        _, _, lora_proj = bc.encode(random_X())
        assert lora_proj.shape == (16, 4)

    def test_lora_proj_is_copy_of_last_W_O(self):
        """lora_proj must match W_O[:, :lora_rank] of the last attention layer."""
        bc = make_clipper(d=16, lora_rank=4)
        _, _, lora_proj = bc.encode(random_X())
        expected = bc.layers[-1].W_O[:, :4]
        np.testing.assert_array_equal(lora_proj, expected)

    def test_single_node(self):
        bc = make_clipper(d=16)
        X = np.ones((1, 16), dtype=np.float64)
        H, tau, lora_proj = bc.encode(X)
        assert H.shape == (1, 16)
        assert tau > 0.0
        assert lora_proj.shape == (16, 4)

    def test_large_N(self):
        bc = make_clipper(d=16)
        X = random_X(N=64, d=16)
        H, tau, lora_proj = bc.encode(X)
        assert H.shape == (64, 16)


# ===========================================================================
# Determinism
# ===========================================================================

class TestEncodeDeterminism:
    def test_same_input_same_output(self):
        bc = make_clipper()
        X = random_X()
        H1, tau1, lp1 = bc.encode(X)
        H2, tau2, lp2 = bc.encode(X)
        np.testing.assert_array_equal(H1, H2)
        assert tau1 == tau2
        np.testing.assert_array_equal(lp1, lp2)

    def test_different_inputs_different_H(self):
        bc = make_clipper()
        X1 = random_X(N=4, d=16)
        X2 = random_X(N=4, d=16) + 10.0
        H1, _, _ = bc.encode(X1)
        H2, _, _ = bc.encode(X2)
        assert not np.allclose(H1, H2)


# ===========================================================================
# update() — perpetual pretraining
# ===========================================================================

class TestUpdate:
    def test_update_returns_float(self):
        bc = make_clipper()
        loss = bc.update(random_X(), lr=1e-4)
        assert isinstance(loss, float)
        assert math.isfinite(loss)
        assert loss >= 0.0

    def test_update_changes_W_emb(self):
        bc = make_clipper()
        W_before = bc.W_emb.copy()
        bc.update(random_X(), lr=1e-3)
        assert not np.allclose(bc.W_emb, W_before)

    def test_update_changes_W_out(self):
        bc = make_clipper()
        W_before = bc.W_out.copy()
        bc.update(random_X(), lr=1e-3)
        assert not np.allclose(bc.W_out, W_before)

    def test_attention_weights_unchanged_after_update(self):
        """Only W_emb and W_out are updated; attention matrices stay frozen."""
        bc = make_clipper()
        W_Q_before = bc.layers[0].W_Q.copy()
        W_O_before = bc.layers[-1].W_O.copy()
        bc.update(random_X(), lr=1e-3)
        np.testing.assert_array_equal(bc.layers[0].W_Q, W_Q_before)
        np.testing.assert_array_equal(bc.layers[-1].W_O, W_O_before)

    def test_gradient_clipping_limits_weight_change(self):
        """With a tiny lr and clip_norm=0.01, weight changes must be bounded."""
        bc = BERTClipper(d_in=16, d=16, n_heads=4, lora_rank=4, clip_norm=0.01, rng=np.random.default_rng(1))
        # Huge X to provoke large gradient
        X = np.ones((6, 16), dtype=np.float64) * 1e4
        W_before = bc.W_emb.copy()
        bc.update(X, lr=1.0, noise_std=0.0)
        delta_norm = float(np.linalg.norm(bc.W_emb - W_before))
        # With clip_norm=0.01 and lr=1.0, max change ≤ clip_norm
        assert delta_norm < 0.1 + 1e-6  # generous bound given two matrices share the budget

    def test_explicit_target(self):
        bc = make_clipper()
        X = random_X()
        target = np.zeros_like(X)
        loss = bc.update(X, target=target, lr=1e-4)
        assert math.isfinite(loss)

    def test_multiple_steps_loss_finite(self):
        bc = make_clipper()
        X = random_X()
        for _ in range(10):
            loss = bc.update(X, lr=1e-4)
            assert math.isfinite(loss)


# ===========================================================================
# n_params
# ===========================================================================

class TestNParams:
    def test_n_params_positive(self):
        bc = make_clipper()
        assert bc.n_params > 0

    def test_n_params_scales_with_d(self):
        bc16 = make_clipper(d=16)
        bc32 = BERTClipper(d_in=32, d=32, n_heads=4, lora_rank=4)
        assert bc32.n_params > bc16.n_params


# ===========================================================================
# d_in ≠ d
# ===========================================================================

class TestNonSquareEmbed:
    def test_d_in_less_than_d(self):
        bc = BERTClipper(d_in=8, d=16, n_heads=4, lora_rank=4, rng=np.random.default_rng(5))
        X = np.random.default_rng(5).standard_normal((4, 8)).astype(np.float64)
        H, tau, lp = bc.encode(X)
        assert H.shape == (4, 16)
        assert tau > 0.0
        assert lp.shape == (16, 4)


# ===========================================================================
# Package import
# ===========================================================================

class TestPackageImport:
    def test_import_from_models(self):
        assert BERTClipperFromPackage is BERTClipper


# ===========================================================================
# TracerDaemon integration — bert + lora_proj properties
# ===========================================================================

class TestTracerDaemonBERTIntegration:
    def _ring_A(self, N: int = 6) -> np.ndarray:
        A = np.zeros((N, N))
        for i in range(N):
            A[i, (i + 1) % N] = 1.0
            A[(i + 1) % N, i] = 1.0
        return A

    def test_daemon_has_bert_property(self):
        from engine.tracer_daemon import TracerDaemon
        d = TracerDaemon(d=16)
        assert isinstance(d.bert, BERTClipper)

    def test_lora_proj_none_before_first_tick(self):
        from engine.tracer_daemon import TracerDaemon
        d = TracerDaemon(d=16)
        assert d.lora_proj is None

    def test_lora_proj_set_after_run_once(self):
        from engine.tracer_daemon import TracerDaemon
        d = TracerDaemon(d=16)
        d.run_once(self._ring_A())
        assert d.lora_proj is not None
        assert d.lora_proj.shape == (16, 8)

    def test_lora_proj_matches_last_W_O_slice(self):
        from engine.tracer_daemon import TracerDaemon
        daemon = TracerDaemon(d=16)
        daemon.run_once(self._ring_A())
        expected = daemon.bert.layers[-1].W_O[:, :8]
        np.testing.assert_array_equal(daemon.lora_proj, expected)

    def test_bert_weights_change_after_run_once(self):
        """Perpetual pretraining: W_emb must change after one tick."""
        from engine.tracer_daemon import TracerDaemon
        daemon = TracerDaemon(d=16)
        W_before = daemon.bert.W_emb.copy()
        daemon.run_once(self._ring_A())
        assert not np.allclose(daemon.bert.W_emb, W_before)
