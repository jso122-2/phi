"""
OctopusTracer MLP Arms — 8 heads operating on the regression matrix R.

Architecture (LOCKED — pow.md):

    8 arms: PRUNE, GRAFT, CLUSTER, RANK, TAG, RESURFACE, MERGE, SPROUT

    Each arm:   R → [Linear(d, d_hidden) → ReLU → Linear(d_hidden, 1)] → score

    Input:  R ∈ ℝ^(N×d)     regression matrix from regression.py
    Output: scores ∈ ℝ^N    per-node arm score

Parameter budget:
    d=256, d_hidden=256
    per arm: W1 (256×256=65536) + b1 (256) + W2 (256×1=256) + b2 (1) = 66,049
    8 arms: ~528,392  ≈ 400K target (slight over; acceptable)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Arm names (order matters — matches shard assignment in bridge_factory)
# ---------------------------------------------------------------------------

ARM_NAMES: tuple[str, ...] = (
    "PRUNE", "GRAFT", "CLUSTER", "RANK",
    "TAG", "RESURFACE", "MERGE", "SPROUT",
)


@dataclass
class ArmScores:
    """Per-arm score vectors for one forward pass."""
    PRUNE:     np.ndarray
    GRAFT:     np.ndarray
    CLUSTER:   np.ndarray
    RANK:      np.ndarray
    TAG:       np.ndarray
    RESURFACE: np.ndarray
    MERGE:     np.ndarray
    SPROUT:    np.ndarray

    def as_dict(self) -> dict[str, np.ndarray]:
        return {
            "PRUNE":     self.PRUNE,
            "GRAFT":     self.GRAFT,
            "CLUSTER":   self.CLUSTER,
            "RANK":      self.RANK,
            "TAG":       self.TAG,
            "RESURFACE": self.RESURFACE,
            "MERGE":     self.MERGE,
            "SPROUT":    self.SPROUT,
        }

    def mean_scores(self) -> dict[str, float]:
        """Mean score per arm across all N nodes."""
        return {name: float(np.mean(arr)) for name, arr in self.as_dict().items()}


class MLPArm:
    """
    Single MLP arm.

    Parameters
    ----------
    name     : arm name (one of ARM_NAMES)
    d_in     : input dimension (matches SSMCore.d)
    d_hidden : hidden layer width
    rng      : numpy Generator
    """

    def __init__(
        self,
        name: str,
        d_in: int = 256,
        d_hidden: int = 256,
        rng: Optional[np.random.Generator] = None,
    ) -> None:
        if name not in ARM_NAMES:
            raise ValueError(f"Unknown arm {name!r}. Valid: {ARM_NAMES}")
        self.name = name
        self.d_in = d_in
        self.d_hidden = d_hidden
        rng = rng or np.random.default_rng(hash(name) & 0xFFFF_FFFF)

        scale = np.sqrt(2.0 / d_in)        # He init for ReLU
        self.W1: np.ndarray = rng.standard_normal((d_hidden, d_in)).astype(np.float64) * scale
        self.b1: np.ndarray = np.zeros(d_hidden, dtype=np.float64)
        self.W2: np.ndarray = rng.standard_normal((1, d_hidden)).astype(np.float64) * np.sqrt(2.0 / d_hidden)
        self.b2: np.ndarray = np.zeros(1, dtype=np.float64)

    @property
    def n_params(self) -> int:
        return (self.d_in * self.d_hidden + self.d_hidden
                + self.d_hidden + 1)

    def forward(self, R: np.ndarray) -> np.ndarray:
        """
        Parameters
        ----------
        R : ndarray, shape (N, d_in)

        Returns
        -------
        scores : ndarray, shape (N,)
        """
        R = np.asarray(R, dtype=np.float64)
        h = np.maximum(0.0, R @ self.W1.T + self.b1)   # (N, d_hidden)
        out = h @ self.W2.T + self.b2                    # (N, 1)
        return out[:, 0]                                 # (N,)

    def __repr__(self) -> str:
        return f"<MLPArm {self.name!r} d_in={self.d_in} d_hidden={self.d_hidden}>"


class OctopusArms:
    """
    All 8 MLP arms bundled together.

    Parameters
    ----------
    d_in     : input dimension (matches SSMCore.d, default 256)
    d_hidden : hidden dim per arm (default 256)
    rng      : numpy Generator
    """

    def __init__(
        self,
        d_in: int = 256,
        d_hidden: int = 256,
        rng: Optional[np.random.Generator] = None,
    ) -> None:
        rng = rng or np.random.default_rng(42)
        self.arms: dict[str, MLPArm] = {
            name: MLPArm(name, d_in=d_in, d_hidden=d_hidden, rng=rng)
            for name in ARM_NAMES
        }
        self.d_in = d_in

    @property
    def n_params(self) -> int:
        return sum(a.n_params for a in self.arms.values())

    def forward(self, R: np.ndarray) -> ArmScores:
        """
        Run all 8 arms on R.

        Parameters
        ----------
        R : ndarray, shape (N, d_in)

        Returns
        -------
        ArmScores — per-node score vector per arm
        """
        R = np.asarray(R, dtype=np.float64)
        scores = {name: self.arms[name].forward(R) for name in ARM_NAMES}
        return ArmScores(**scores)

    def save(self, path: str | Path) -> None:
        """Persist all 8 arm weight matrices to an npz."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, np.ndarray] = {
            "d_in": np.array(self.d_in),
            "d_hidden": np.array(next(iter(self.arms.values())).d_hidden),
        }
        for name, arm in self.arms.items():
            payload[f"{name}_W1"] = arm.W1
            payload[f"{name}_b1"] = arm.b1
            payload[f"{name}_W2"] = arm.W2
            payload[f"{name}_b2"] = arm.b2
        np.savez(path, **payload)

    @classmethod
    def load(cls, path: str | Path) -> "OctopusArms":
        """Load weights written by save()."""
        data = np.load(path)
        d_in = int(data["d_in"])
        d_hidden = int(data["d_hidden"])
        inst = cls.__new__(cls)
        inst.d_in = d_in
        inst.arms = {}
        for name in ARM_NAMES:
            arm = MLPArm.__new__(MLPArm)
            arm.name = name
            arm.d_in = d_in
            arm.d_hidden = d_hidden
            arm.W1 = np.asarray(data[f"{name}_W1"], dtype=np.float64)
            arm.b1 = np.asarray(data[f"{name}_b1"], dtype=np.float64)
            arm.W2 = np.asarray(data[f"{name}_W2"], dtype=np.float64)
            arm.b2 = np.asarray(data[f"{name}_b2"], dtype=np.float64)
            inst.arms[name] = arm
        return inst

    @classmethod
    def load_default(
        cls,
        d_in: int = 256,
        path: str | Path | None = None,
    ) -> "OctopusArms":
        ckpt = Path(path) if path is not None else Path.home() / ".phi" / "octopus_arms.npz"
        if ckpt.exists():
            return cls.load(ckpt)
        return cls(d_in=d_in)

    def __repr__(self) -> str:
        return f"<OctopusArms d_in={self.d_in} n_arms=8 n_params={self.n_params:,}>"
