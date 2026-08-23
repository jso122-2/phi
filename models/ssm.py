"""
SSM Core — tick-synchronised state-space model for OctopusTracer.

Architecture (LOCKED — pow.md):

    Takes node embeddings X ∈ ℝ^(N×d) at each tick.
    Emits:
      H   ∈ ℝ^(N×d)  — hidden state per node, updated each tick
      tau ∈ ℝ⁺       — temperature (used in SCUP cosine)

Parameter budget target: ~900K at d=256.

Layer structure (4 SSM layers):
  Per layer: A (d×d) + B (d×d) + C (d×d) + bias_a (d) + bias_c (d)
  Params per layer:  3 × d² + 2d  = 3×65536 + 512 = 197,120
  4 layers:          788,480
  tau (1 scalar):    1
  Total:             ~788K  (target ≤ 900K  ✓)

State update per layer (left-to-right through the sequence):
    h = tanh(x @ B.T + h_prev @ A.T + bias_a)
    y = h @ C.T + bias_c
    x (next layer) = y

Final output: H = y_last  (N×d),  tau = softplus(log_tau)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class SSMLayerParams:
    """Weight tensors for one SSM layer."""
    A: np.ndarray          # (d, d)  state transition
    B: np.ndarray          # (d, d)  input projection
    C: np.ndarray          # (d, d)  output projection
    bias_a: np.ndarray     # (d,)
    bias_c: np.ndarray     # (d,)


class SSMCore:
    """
    Multi-layer numpy SSM core.

    Parameters
    ----------
    d          : embedding / state dimension (default 256)
    n_layers   : number of stacked SSM layers (default 4)
    rng        : numpy Generator (default: new default_rng())
    """

    def __init__(
        self,
        d: int = 256,
        n_layers: int = 4,
        rng: Optional[np.random.Generator] = None,
    ) -> None:
        self.d = d
        self.n_layers = n_layers
        rng = rng or np.random.default_rng(0)

        scale = 0.02
        self.layers: list[SSMLayerParams] = [
            SSMLayerParams(
                A=rng.standard_normal((d, d)).astype(np.float64) * scale,
                B=rng.standard_normal((d, d)).astype(np.float64) * scale,
                C=rng.standard_normal((d, d)).astype(np.float64) * scale,
                bias_a=np.zeros(d, dtype=np.float64),
                bias_c=np.zeros(d, dtype=np.float64),
            )
            for _ in range(n_layers)
        ]

        # Learnable log-temperature; tau = softplus(log_tau) > 0
        self._log_tau: float = 0.0   # softplus(0) ≈ 0.693 → decent initial temperature

        # Persistent hidden state per node — reset when node count changes
        self._h: Optional[np.ndarray] = None   # shape (N, d)
        self._n_nodes: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def tau(self) -> float:
        """Current temperature: softplus(log_tau) = log(1 + exp(log_tau))."""
        return float(np.log1p(np.exp(self._log_tau)))

    @property
    def n_params(self) -> int:
        """Total number of scalar parameters."""
        per_layer = 3 * self.d * self.d + 2 * self.d
        return self.n_layers * per_layer + 1  # +1 for log_tau

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def reset_state(self, n_nodes: int) -> None:
        """Initialise (or re-initialise) the hidden state for n_nodes nodes."""
        self._h = np.zeros((n_nodes, self.d), dtype=np.float64)
        self._n_nodes = n_nodes

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------

    def tick(self, X: np.ndarray) -> tuple[np.ndarray, float]:
        """
        One SSM tick.

        Parameters
        ----------
        X : ndarray, shape (N, d)
            Node embeddings for this tick.

        Returns
        -------
        H   : ndarray, shape (N, d)  — updated hidden states
        tau : float                  — current temperature
        """
        X = np.asarray(X, dtype=np.float64)
        N, d_in = X.shape
        if d_in != self.d:
            raise ValueError(f"Expected d={self.d}, got {d_in}")

        if self._h is None or self._n_nodes != N:
            self.reset_state(N)

        h = self._h.copy()
        x = X

        for layer in self.layers:
            h_new = np.tanh(x @ layer.B.T + h @ layer.A.T + layer.bias_a)
            y = h_new @ layer.C.T + layer.bias_c
            h = h_new
            x = y

        self._h = h
        return x, self.tau

    # ------------------------------------------------------------------
    # Temperature update
    # ------------------------------------------------------------------

    def update_tau(self, delta: float) -> None:
        """Shift log_tau by delta (positive → warmer, negative → cooler)."""
        self._log_tau += delta

    def save(self, path: str | Path) -> None:
        """Persist layer weights + log_tau to an npz."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, np.ndarray] = {
            "d": np.array(self.d),
            "n_layers": np.array(self.n_layers),
            "log_tau": np.array(self._log_tau),
        }
        for i, layer in enumerate(self.layers):
            payload[f"L{i}_A"] = layer.A
            payload[f"L{i}_B"] = layer.B
            payload[f"L{i}_C"] = layer.C
            payload[f"L{i}_bias_a"] = layer.bias_a
            payload[f"L{i}_bias_c"] = layer.bias_c
        np.savez(path, **payload)

    @classmethod
    def load(cls, path: str | Path) -> "SSMCore":
        """Load weights written by save()."""
        data = np.load(path)
        d = int(data["d"])
        n_layers = int(data["n_layers"])
        inst = cls.__new__(cls)
        inst.d = d
        inst.n_layers = n_layers
        inst._log_tau = float(data["log_tau"])
        inst._h = None
        inst._n_nodes = 0
        inst.layers = [
            SSMLayerParams(
                A=np.asarray(data[f"L{i}_A"], dtype=np.float64),
                B=np.asarray(data[f"L{i}_B"], dtype=np.float64),
                C=np.asarray(data[f"L{i}_C"], dtype=np.float64),
                bias_a=np.asarray(data[f"L{i}_bias_a"], dtype=np.float64),
                bias_c=np.asarray(data[f"L{i}_bias_c"], dtype=np.float64),
            )
            for i in range(n_layers)
        ]
        return inst

    @classmethod
    def load_default(
        cls,
        d: int = 256,
        n_layers: int = 4,
        path: str | Path | None = None,
    ) -> "SSMCore":
        ckpt = Path(path) if path is not None else Path.home() / ".phi" / "ssm_core.npz"
        if ckpt.exists():
            return cls.load(ckpt)
        return cls(d=d, n_layers=n_layers)

    def __repr__(self) -> str:
        return (
            f"<SSMCore d={self.d} n_layers={self.n_layers} "
            f"n_params≈{self.n_params:,} tau={self.tau:.4f}>"
        )
