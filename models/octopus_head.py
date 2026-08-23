"""
OctopusAttentionHead — bilinear complement-adjacency attention.

Formula (ARCHITECTURE LOCKED — pow.md):

    output = Ā̅ @ diag(v_d) @ Ā̅ᵀ − fs

where
    Ā̅   ∈ {0,1}^(N×N)  complement adjacency matrix  (direct MLP input)
    v   ∈ ℝ^N           direction beta vector
    d   ∈ ℝ^N           drift component derivative
    v_d = v ⊙ d         elementwise product → diagonal of the attention kernel
    fs  ∈ ℝ             fixed set scalar, hard-clipped < 24.0 (23.999 recurring)

The operator is matrix multiply.  Ā̅ is the adjacency of the complement graph
G̅ = complement(G).  The result is an N×N attention score matrix.

fs_max = 23.999... (repeating) → clips at FS_MAX_EXCLUSIVE = 24.0 - ε.

This is the canonical entry point:

    from models import OctopusAttentionHead
"""

from __future__ import annotations

import numpy as np

# 23.999... (repeating 9) = 24 in the limit — cap strictly below
FS_MAX_EXCLUSIVE: float = 24.0 - 1e-9


class OctopusAttentionHead:
    """
    Bilinear complement-adjacency attention head.

    Parameters
    ----------
    fs : float
        Fixed set scalar.  Clamped to [0, FS_MAX_EXCLUSIVE) at construction.
    """

    def __init__(self, fs: float = 0.0) -> None:
        if fs >= FS_MAX_EXCLUSIVE:
            fs = FS_MAX_EXCLUSIVE - 1e-12
        self.fs: float = float(fs)

    # ------------------------------------------------------------------
    # Core forward
    # ------------------------------------------------------------------

    def forward(
        self,
        A_bar: np.ndarray,
        v: np.ndarray,
        d: np.ndarray,
    ) -> np.ndarray:
        """
        Compute  output = Ā̅ @ diag(v_d) @ Ā̅ᵀ − fs

        Parameters
        ----------
        A_bar : ndarray, shape (N, N)
            Complement adjacency matrix (binary).
        v : ndarray, shape (N,)
            Direction beta vector.
        d : ndarray, shape (N,)
            Drift component derivative.

        Returns
        -------
        ndarray, shape (N, N)
            Attention score matrix.
        """
        A_bar = np.asarray(A_bar, dtype=float)
        v = np.asarray(v, dtype=float)
        d = np.asarray(d, dtype=float)

        v_d = v * d                                      # (N,) diagonal entries
        # Ā̅ @ diag(v_d) @ Ā̅ᵀ  implemented without materialising full diag matrix
        # Equivalent to (A_bar * v_d[np.newaxis, :]) @ A_bar.T
        return (A_bar * v_d[np.newaxis, :]) @ A_bar.T - self.fs

    # ------------------------------------------------------------------
    # fs update
    # ------------------------------------------------------------------

    def set_fs(self, value: float) -> None:
        """Update the fixed set scalar; enforces the < 24 ceiling."""
        if value >= FS_MAX_EXCLUSIVE:
            value = FS_MAX_EXCLUSIVE - 1e-12
        self.fs = float(value)

    def __repr__(self) -> str:
        return f"<OctopusAttentionHead fs={self.fs:.6g}>"
