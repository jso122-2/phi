"""
Tests for models.suckers.LoRASucker and SuckerPool (15 tests).

Coverage:
  - B=0 init means output is zero at spawn
  - One gradient step makes output non-zero
  - Warm-start from BERT projection weight (both row and transposed layouts)
  - Pool spawns above threshold, silent below
  - Device-agnostic: suckers operate on plain numpy arrays
"""
from __future__ import annotations

import numpy as np
import pytest

from models.suckers import LoRASucker, SuckerPool, SpawnEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_sucker(d: int = 32, rank: int = 4, **kw) -> LoRASucker:
    return LoRASucker(d=d, rank=rank, **kw)


def random_R(N: int = 8, d: int = 32, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal((N, d))


# ===========================================================================
# B=0 init
# ===========================================================================

class TestBZeroInit:
    def test_B_is_zero_at_spawn(self):
        s = make_sucker()
        np.testing.assert_array_equal(s.B, np.zeros_like(s.B))

    def test_output_is_zero_at_spawn(self):
        d, N = 32, 8
        s = make_sucker(d=d)
        x = random_R(N=N, d=d)
        out = s.forward(x)
        np.testing.assert_allclose(out, np.zeros((N, d)), atol=1e-12)

    def test_is_active_false_before_update(self):
        s = make_sucker()
        assert not s.is_active


# ===========================================================================
# One gradient step
# ===========================================================================

class TestGradientStep:
    def test_one_step_makes_output_nonzero(self):
        d, N = 32, 8
        s = make_sucker(d=d, rank=4)
        x = random_R(N=N, d=d)
        target = np.ones((N, d))
        s.update(x, target, lr=1e-2)
        out = s.forward(x)
        assert not np.allclose(out, 0.0)

    def test_is_active_after_update(self):
        d, N = 32, 8
        s = make_sucker(d=d)
        x = random_R(N=N, d=d)
        s.update(x, np.ones((N, d)), lr=1e-2)
        assert s.is_active

    def test_loss_returned_from_update(self):
        d, N = 16, 4
        s = make_sucker(d=d)
        x = random_R(N=N, d=d)
        loss = s.update(x, np.ones((N, d)), lr=1e-2)
        assert isinstance(loss, float)
        assert loss >= 0.0

    def test_repeated_steps_reduce_loss(self):
        d, N = 16, 4
        s = make_sucker(d=d, rank=4)
        rng = np.random.default_rng(7)
        x = rng.standard_normal((N, d))
        target = rng.standard_normal((N, d))
        losses = [s.update(x, target, lr=1e-1) for _ in range(50)]
        # Loss should generally decrease
        assert losses[-1] < losses[0]


# ===========================================================================
# Warm-start (A_init)
# ===========================================================================

class TestWarmStart:
    def test_row_layout_accepted(self):
        d, rank = 32, 4
        A_init = np.random.default_rng(0).standard_normal((d, rank))
        s = LoRASucker(d=d, rank=rank, A_init=A_init)
        np.testing.assert_array_equal(s.A, A_init)

    def test_transposed_layout_accepted(self):
        d, rank = 32, 4
        A_init_T = np.random.default_rng(1).standard_normal((rank, d))
        s = LoRASucker(d=d, rank=rank, A_init=A_init_T)
        np.testing.assert_array_equal(s.A, A_init_T.T)

    def test_incompatible_shape_raises(self):
        with pytest.raises(ValueError, match="incompatible"):
            LoRASucker(d=32, rank=4, A_init=np.ones((5, 5)))

    def test_warmstart_B_still_zero(self):
        d, rank = 16, 4
        A_init = np.eye(d)[:, :rank]
        s = LoRASucker(d=d, rank=rank, A_init=A_init)
        np.testing.assert_array_equal(s.B, np.zeros_like(s.B))


# ===========================================================================
# SuckerPool spawn logic
# ===========================================================================

class TestSuckerPool:
    def test_spawn_above_threshold(self):
        d, rank = 16, 4
        pool = SuckerPool(d=d, rank=rank, theta=0.5, max_suckers=8)
        R = 10.0 * np.ones((4, d))   # ‖R(u)‖ >> threshold
        spawned = pool.maybe_spawn(R, arm_name="SPROUT")
        assert spawned is True
        assert pool.n_live == 1

    def test_silent_below_threshold(self):
        d, rank = 16, 4
        pool = SuckerPool(d=d, rank=rank, theta=100.0, max_suckers=8)
        R = np.zeros((4, d))
        spawned = pool.maybe_spawn(R, arm_name="PRUNE")
        assert spawned is False
        assert pool.n_live == 0

    def test_max_suckers_cap_respected(self):
        d, rank = 16, 4
        pool = SuckerPool(d=d, rank=rank, theta=0.0, max_suckers=3)
        R = 10.0 * np.ones((4, d))
        for _ in range(10):
            pool.maybe_spawn(R)
        assert pool.n_live <= 3

    def test_forward_all_zero_before_updates(self):
        d, rank = 16, 4
        pool = SuckerPool(d=d, rank=rank, theta=0.0, max_suckers=4)
        R = 10.0 * np.ones((3, d))
        pool.maybe_spawn(R)
        x = np.ones((3, d))
        out = pool.forward_all(x)
        np.testing.assert_allclose(out, np.zeros((3, d)), atol=1e-12)

    def test_device_agnostic_float32(self):
        d = 16
        pool = SuckerPool(d=d, rank=4, theta=0.0, max_suckers=4)
        R = np.ones((3, d), dtype=np.float32)
        pool.maybe_spawn(R)   # should not raise
        out = pool.forward_all(R)
        assert out.dtype == np.float64   # suckers operate in float64

    def test_spawn_log_records_event(self):
        d = 16
        pool = SuckerPool(d=d, rank=4, theta=0.5, max_suckers=8)
        R = 10.0 * np.ones((2, d))
        pool.maybe_spawn(R, arm_name="TAG")
        assert len(pool.spawn_log) == 1
        ev = pool.spawn_log[0]
        assert ev.arm_name == "TAG"
        assert ev.norm_at_spawn > 0.5
