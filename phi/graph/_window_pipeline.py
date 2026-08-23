"""phi.graph._window_pipeline — list[SongNode] → regression tensors.

Bridges the phi graph layer to the OctopusTracer regression pipeline.

The regression pipeline (models/regression.py) needs three things:

    A     ∈ {0,1}^(N×N)   adjacency of G (window-local)
    H     ∈ ℝ^(N×d)       hidden states per node
    tau   ∈ ℝ⁺            temperature

This module produces all three from a list[SongNode] returned by
PhiGraphSnapshot.window() or build_window().

Public API
----------
    tensors = build_window_tensors(nodes)
        → WindowTensors(A, A_bar, H_phi)

    result  = run_window(nodes, ssm)
        → WindowResult(R, A_bar, Theta, F, H_ssm, tau)
        Full pipeline: Phi embeddings → SSM tick → compute_R.

Adjacency
---------
    Primary   : tag-Jaccard  (uses Track.all_tags, existing _tag_adjacency)
    Secondary : audio cosine (uses AudioFeatures.to_vector(), added here)
                # TODO(suggestion): expose audio adjacency via run_window flag
                  once AudioFeatures are populated via librosa in production.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from phi._track import Track
from phi.graph._adjacency import _tag_adjacency
from phi.metadata.schema import SongNode

__all__ = [
    "WindowTensors",
    "WindowResult",
    "build_window_tensors",
    "run_window",
]


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class WindowTensors:
    """Raw tensors extracted from a list[SongNode].

    These are the direct inputs to compute_R() and OctopusAttentionHead.

    Fields
    ------
    A      : (N, N) binary tag-Jaccard adjacency for the window
    A_bar  : (N, N) complement adjacency  Ā̅ = J − I − A  (diag 0)
    H_phi  : (N, 256) Phi embeddings stacked from position.h_u
    nodes  : the source SongNode list (preserved for downstream use)
    """
    A: np.ndarray        # (N, N)
    A_bar: np.ndarray    # (N, N)
    H_phi: np.ndarray    # (N, 256)
    nodes: list[SongNode]

    @property
    def N(self) -> int:
        return len(self.nodes)


@dataclass
class WindowResult:
    """Full regression pipeline output for one window.

    Produced by run_window().

    Fields
    ------
    R      : (N, d) regression matrix  →  direct input to OctopusArms
    A_bar  : (N, N) complement adjacency  →  input to OctopusAttentionHead
    Theta  : (N, N) angular distance matrix
    F      : (N, d) tangent flow
    H_ssm  : (N, d) SSM hidden states (post-tick)
    tau    : float  temperature emitted by SSMCore
    """
    R: np.ndarray       # (N, d)
    A_bar: np.ndarray   # (N, N)
    Theta: np.ndarray   # (N, N)
    F: np.ndarray       # (N, d)
    H_ssm: np.ndarray   # (N, d)
    tau: float


# ---------------------------------------------------------------------------
# Adjacency helpers
# ---------------------------------------------------------------------------

def _complement(A: np.ndarray) -> np.ndarray:
    """Ā̅ = J − I − A with diagonal forced to zero."""
    A = np.asarray(A, dtype=np.float64)
    A_bar = 1.0 - A
    np.fill_diagonal(A_bar, 0.0)
    return A_bar


def _audio_adjacency(nodes: list[SongNode], threshold: float = 0.80) -> np.ndarray:
    """Build (N, N) adjacency from cosine similarity of AudioFeatures vectors.

    Edge (u, v) when cosine_similarity(a_u, a_v) > threshold.

    Parameters
    ----------
    nodes     : list[SongNode] — audio.to_vector() must be non-trivially populated
    threshold : similarity cutoff in (0, 1); default 0.80

    Returns
    -------
    A_audio : (N, N) binary float64, diagonal 0
    """
    vecs = np.stack([n.audio.to_vector() for n in nodes], axis=0)  # (N, 30)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.where(norms < 1e-12, 1e-12, norms)
    normed = vecs / norms
    sims = normed @ normed.T                                         # (N, N)
    A_audio = (sims > threshold).astype(np.float64)
    np.fill_diagonal(A_audio, 0.0)
    return A_audio


# ---------------------------------------------------------------------------
# Primary entry point
# ---------------------------------------------------------------------------

def build_window_tensors(
    nodes: list[SongNode],
    tag_threshold: float = 0.10,
) -> WindowTensors:
    """Extract (A, Ā̅, H_phi) from a list[SongNode].

    This is the bridge from the phi graph layer to the regression pipeline.

    Parameters
    ----------
    nodes         : list[SongNode] from PhiGraphSnapshot.window() or build_window()
                    position.h_u must be populated (i.e., window() was called, not
                    build_window with extract_audio=False only).
    tag_threshold : Jaccard threshold for adjacency edges (default 0.10)

    Returns
    -------
    WindowTensors
        .A      (N, N) binary adjacency
        .A_bar  (N, N) complement adjacency — direct MLP input for OctopusAttentionHead
        .H_phi  (N, 256) Phi embeddings, L2-normed (from position.h_u)

    Raises
    ------
    ValueError if nodes is empty or exceeds WINDOW_SIZE
    """
    from phi.metadata.schema import WINDOW_SIZE

    if not nodes:
        raise ValueError("nodes must be non-empty.")
    if len(nodes) > WINDOW_SIZE:
        raise ValueError(
            f"Window size is fixed at {WINDOW_SIZE}; got {len(nodes)} nodes."
        )

    tracks: list[Track] = [n.track for n in nodes]
    A = _tag_adjacency(tracks, tag_threshold)
    A_bar = _complement(A)

    # Stack h_u from each node's GraphPosition — these are the Phi embeddings
    # written by PhiGraphSnapshot.window() from H[global_idx].
    H_phi = np.stack(
        [np.asarray(n.position.h_u, dtype=np.float64) for n in nodes],
        axis=0,
    )  # (N, 256)

    return WindowTensors(A=A, A_bar=A_bar, H_phi=H_phi, nodes=nodes)


# ---------------------------------------------------------------------------
# Full pipeline runner
# ---------------------------------------------------------------------------

def run_window(
    nodes: list[SongNode],
    ssm: "SSMCore",  # type: ignore[name-defined]  # avoid circular at module level
    tag_threshold: float = 0.10,
) -> WindowResult:
    """Run the full OctopusTracer regression pipeline on a 6-node window.

    Chain:
        list[SongNode]
          → build_window_tensors()  →  A, Ā̅, H_phi
          → SSMCore.tick(H_phi)     →  H_ssm, tau
          → compute_R(A, H_ssm, tau) → R, A_bar, Theta, F

    Parameters
    ----------
    nodes         : list[SongNode] with h_u populated (from snapshot.window())
    ssm           : SSMCore instance (tick-synchronised with CAIRRN)
    tag_threshold : Jaccard threshold for window adjacency

    Returns
    -------
    WindowResult
        .R      (N, d) — feed this directly to OctopusArms.forward(R)
        .A_bar  (N, N) — feed to OctopusAttentionHead.forward(A_bar, v, d)
        .Theta  (N, N) — angular distance (intermediate)
        .F      (N, d) — tangent flow (intermediate)
        .H_ssm  (N, d) — SSM hidden states after this tick
        .tau    float  — temperature for this tick
    """
    from models.regression import compute_R

    tensors = build_window_tensors(nodes, tag_threshold=tag_threshold)
    H_ssm, tau = ssm.tick(tensors.H_phi)
    R, A_bar, Theta, F = compute_R(tensors.A, H_ssm, tau)

    return WindowResult(
        R=R,
        A_bar=A_bar,
        Theta=Theta,
        F=F,
        H_ssm=H_ssm,
        tau=tau,
    )
