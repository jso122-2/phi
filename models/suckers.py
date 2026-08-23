"""
LoRA Sucker Layer — unbounded elastic LoRA for OctopusTracer.

Architecture (LOCKED — pow.md):

    Spawn condition:  ‖R(u)‖ > θ  → spawn sucker on relevant arm
    Sucker init:      inherits BERT clipper weights at spawn (or random A)
                      B = 0  → output is zero at spawn
    Specialisation:   updates on local subgraph neighbourhood

LoRA structure:
    A ∈ ℝ^(d×r)   — fixed at spawn (initialised from projection weights or random)
    B ∈ ℝ^(r×d)   — zero at spawn; updated by gradient steps
    forward(x) = x @ A @ B    ∈ ℝ^(N×d)

Because B=0 at init:  output = x @ A @ 0 = 0.
One gradient step on B makes the output non-zero.

Manual gradient for MSE loss  L = ‖x@A@B − target‖²_F:
    ∂L/∂B = (A.T @ x.T @ (x@A@B − target)) / N

Device-agnostic: suckers always operate on plain numpy float64 arrays.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Individual sucker
# ---------------------------------------------------------------------------

class LoRASucker:
    """
    One LoRA sucker specialised to a complement-graph neighbourhood.

    Parameters
    ----------
    d         : embedding / state dimension (must match SSMCore.d)
    rank      : LoRA rank r (default 8)
    arm_name  : which MLP arm spawned this sucker
    A_init    : optional (d, r) array to warm-start A (e.g. BERT projection)
    rng       : numpy Generator
    """

    def __init__(
        self,
        d: int = 256,
        rank: int = 8,
        arm_name: str = "",
        A_init: Optional[np.ndarray] = None,
        rng: Optional[np.random.Generator] = None,
    ) -> None:
        self.d = d
        self.rank = rank
        self.arm_name = arm_name
        rng = rng or np.random.default_rng()

        if A_init is not None:
            A_init = np.asarray(A_init, dtype=np.float64)
            if A_init.shape == (d, rank):
                self.A = A_init.copy()
            elif A_init.shape == (rank, d):
                # transposed layout — row vs column dominant
                self.A = A_init.T.copy()
            else:
                raise ValueError(
                    f"A_init shape {A_init.shape} incompatible with (d={d}, r={rank}) "
                    f"or its transpose"
                )
        else:
            self.A = rng.standard_normal((d, rank)).astype(np.float64) * 0.02

        # B=0 → output is zero at spawn
        self.B = np.zeros((rank, d), dtype=np.float64)

    # ------------------------------------------------------------------

    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        Parameters
        ----------
        x : (N, d)

        Returns
        -------
        out : (N, d)
        """
        x = np.asarray(x, dtype=np.float64)
        return x @ self.A @ self.B      # (N, d); 0 until B is updated

    def update(self, x: np.ndarray, target: np.ndarray, lr: float = 1e-3) -> float:
        """
        One gradient step on B (A stays frozen after spawn).

        Loss: MSE = ‖forward(x) − target‖²_F / N

        Returns
        -------
        loss : float  — MSE before the update
        """
        x = np.asarray(x, dtype=np.float64)
        target = np.asarray(target, dtype=np.float64)
        N = x.shape[0]
        pred = x @ self.A @ self.B
        err = pred - target             # (N, d)
        loss = float(np.mean(err ** 2))
        grad_B = (self.A.T @ (x.T @ err)) / N   # (r, d)
        self.B -= lr * grad_B
        return loss

    @property
    def is_active(self) -> bool:
        """True once B has been updated at least once."""
        return bool(np.any(self.B != 0.0))

    def save(self, path: str | Path) -> None:
        """Persist A, B to an npz."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            path,
            d=np.array(self.d),
            rank=np.array(self.rank),
            arm_name=np.array(self.arm_name),
            A=self.A,
            B=self.B,
        )

    @classmethod
    def load(cls, path: str | Path) -> "LoRASucker":
        data = np.load(path)
        inst = cls.__new__(cls)
        inst.d = int(data["d"])
        inst.rank = int(data["rank"])
        inst.arm_name = str(data["arm_name"])
        inst.A = np.asarray(data["A"], dtype=np.float64)
        inst.B = np.asarray(data["B"], dtype=np.float64)
        return inst

    def __repr__(self) -> str:
        return (
            f"<LoRASucker arm={self.arm_name!r} d={self.d} "
            f"rank={self.rank} active={self.is_active}>"
        )


# ---------------------------------------------------------------------------
# Pool — manages a collection of suckers per arm
# ---------------------------------------------------------------------------

@dataclass
class SpawnEvent:
    """Record of one sucker spawn."""
    arm_name: str
    node_index: int
    norm_at_spawn: float
    sucker_index: int


class SuckerPool:
    """
    Manages LoRA suckers across all arms.

    Spawn rule:  for each node u, if ‖R(u)‖ > theta and pool has headroom,
                 a new sucker is spawned on the arm with the highest score at u.

    Parameters
    ----------
    d           : state dimension
    rank        : LoRA rank per sucker
    theta       : spawn threshold on ‖R(u)‖
    max_suckers : hard cap on total live suckers across all arms
    """

    def __init__(
        self,
        d: int = 256,
        rank: int = 8,
        theta: float = 1.0,
        max_suckers: int = 32,
    ) -> None:
        self.d = d
        self.rank = rank
        self.theta = theta
        self.max_suckers = max_suckers
        self.suckers: list[LoRASucker] = []
        self.spawn_log: list[SpawnEvent] = []

    # ------------------------------------------------------------------

    def maybe_spawn(
        self,
        R: np.ndarray,
        arm_name: str = "SPROUT",
        R_proj: Optional[np.ndarray] = None,
        rng: Optional[np.random.Generator] = None,
    ) -> bool:
        """
        Check each node's ‖R(u)‖; spawn a sucker if above theta and cap allows.

        Parameters
        ----------
        R        : (N, d) regression matrix slice
        arm_name : arm that triggered this spawn check
        R_proj   : optional (d, rank) or (rank, d) warm-start for A
        rng      : optional Generator

        Returns
        -------
        bool — True if at least one sucker was spawned
        """
        R = np.asarray(R, dtype=np.float64)
        norms = np.linalg.norm(R, axis=1)   # (N,)
        spawned = False

        for node_idx, norm in enumerate(norms):
            if norm > self.theta and len(self.suckers) < self.max_suckers:
                s = LoRASucker(
                    d=self.d,
                    rank=self.rank,
                    arm_name=arm_name,
                    A_init=R_proj,
                    rng=rng,
                )
                idx = len(self.suckers)
                self.suckers.append(s)
                self.spawn_log.append(SpawnEvent(
                    arm_name=arm_name,
                    node_index=node_idx,
                    norm_at_spawn=float(norm),
                    sucker_index=idx,
                ))
                spawned = True
                break   # one spawn per call — respect determinism

        return spawned

    def forward_all(self, x: np.ndarray) -> np.ndarray:
        """
        Aggregate output from all live suckers.

        Returns (N, d) zero array if no suckers are active.
        """
        x = np.asarray(x, dtype=np.float64)
        N = x.shape[0]
        out = np.zeros((N, self.d), dtype=np.float64)
        for s in self.suckers:
            out += s.forward(x)
        return out

    def save(self, path: str | Path) -> None:
        """Persist pool hyperparams + every live sucker's A/B."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, np.ndarray] = {
            "d": np.array(self.d),
            "rank": np.array(self.rank),
            "theta": np.array(self.theta),
            "max_suckers": np.array(self.max_suckers),
            "n_live": np.array(len(self.suckers)),
        }
        for i, s in enumerate(self.suckers):
            payload[f"S{i}_A"] = s.A
            payload[f"S{i}_B"] = s.B
            payload[f"S{i}_arm"] = np.array(s.arm_name)
        np.savez(path, **payload)

    @classmethod
    def load(cls, path: str | Path) -> "SuckerPool":
        data = np.load(path)
        inst = cls(
            d=int(data["d"]),
            rank=int(data["rank"]),
            theta=float(data["theta"]),
            max_suckers=int(data["max_suckers"]),
        )
        n_live = int(data["n_live"])
        for i in range(n_live):
            s = LoRASucker.__new__(LoRASucker)
            s.d = inst.d
            s.rank = inst.rank
            s.arm_name = str(data[f"S{i}_arm"])
            s.A = np.asarray(data[f"S{i}_A"], dtype=np.float64)
            s.B = np.asarray(data[f"S{i}_B"], dtype=np.float64)
            inst.suckers.append(s)
        return inst

    @classmethod
    def load_default(cls, d: int = 256, path: str | Path | None = None) -> "SuckerPool":
        ckpt = Path(path) if path is not None else Path.home() / ".phi" / "sucker_pool.npz"
        if ckpt.exists():
            return cls.load(ckpt)
        return cls(d=d)

    @property
    def n_live(self) -> int:
        return len(self.suckers)

    def __repr__(self) -> str:
        return (
            f"<SuckerPool d={self.d} rank={self.rank} "
            f"theta={self.theta} live={self.n_live}/{self.max_suckers}>"
        )
