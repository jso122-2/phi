"""
OctopusTracer Regression Pipeline — closed-form, no learnable parameters.

Steps (ARCHITECTURE LOCKED — pow.md):

    1.  G̅  = complement(G)           ← absence space
    2.  C[u,v] = (h_u·h_v) / (‖h_u‖‖h_v‖τ)  ← SCUP cosine similarity
    3.  Θ  = arccos(clip(C, −1, 1))   ← angular distance
    4.  L̅  = D̅ − Ā̅                   ← complement Laplacian
    5.  F  = L̅ · H                    ← tangent flow
    6.  R  = Θ @ F                    ← regression matrix (MLP input)

All steps are pure numpy — zero learnable parameters.

Input:
    A   ∈ {0,1}^(N×N)   adjacency matrix of the original graph G
    H   ∈ ℝ^(N×d)       hidden states from SSMCore.tick()
    tau ∈ ℝ⁺            temperature from SSMCore

Output:
    R   ∈ ℝ^(N×d)       regression matrix fed to the 8 MLP arms
"""

from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------------------
# Step 1: complement graph
# ---------------------------------------------------------------------------

def complement_graph(A: np.ndarray) -> np.ndarray:
    """
    Complement adjacency matrix  Ā̅ = (J − I − A),  where
    J = all-ones matrix, I = identity.

    Diagonal is forced to zero (no self-loops in complement).

    Parameters
    ----------
    A : ndarray, shape (N, N)
        Binary adjacency matrix of G.

    Returns
    -------
    A_bar : ndarray, shape (N, N)
        Binary adjacency matrix of G̅.
    """
    A = np.asarray(A, dtype=float)
    N = A.shape[0]
    A_bar = 1.0 - A
    np.fill_diagonal(A_bar, 0.0)
    return A_bar


# ---------------------------------------------------------------------------
# Step 2: SCUP cosine similarity
# ---------------------------------------------------------------------------

def scup_cosine(H: np.ndarray, tau: float) -> np.ndarray:
    """
    SCUP cosine similarity matrix.

    C[u,v] = (h_u · h_v) / (‖h_u‖ · ‖h_v‖ · τ)

    Parameters
    ----------
    H   : ndarray, shape (N, d)
    tau : float  temperature > 0

    Returns
    -------
    C : ndarray, shape (N, N)  — values in [−1/τ, 1/τ]
    """
    H = np.asarray(H, dtype=float)
    norms = np.linalg.norm(H, axis=1, keepdims=True)         # (N, 1)
    norms = np.where(norms < 1e-12, 1e-12, norms)            # avoid /0
    H_norm = H / norms                                         # (N, d) unit rows
    tau = max(float(tau), 1e-9)
    return (H_norm @ H_norm.T) / tau                          # (N, N)


# ---------------------------------------------------------------------------
# Step 3: angular distance
# ---------------------------------------------------------------------------

def angular_dist(C: np.ndarray) -> np.ndarray:
    """
    Angular distance  Θ = arccos(clip(C, −1, 1)).

    Parameters
    ----------
    C : ndarray, shape (N, N)  — SCUP cosine similarity matrix

    Returns
    -------
    Theta : ndarray, shape (N, N)  — values in [0, π]
    """
    return np.arccos(np.clip(C, -1.0, 1.0))


# ---------------------------------------------------------------------------
# Step 4: complement Laplacian
# ---------------------------------------------------------------------------

def complement_laplacian(A_bar: np.ndarray) -> np.ndarray:
    """
    Complement Laplacian  L̅ = D̅ − Ā̅,

    where D̅ = diag(Ā̅ · 1)  (degree matrix of the complement graph).

    Parameters
    ----------
    A_bar : ndarray, shape (N, N)  — complement adjacency

    Returns
    -------
    L_bar : ndarray, shape (N, N)
    """
    A_bar = np.asarray(A_bar, dtype=float)
    d_bar = A_bar.sum(axis=1)     # (N,)  complement-degree per node
    D_bar = np.diag(d_bar)
    return D_bar - A_bar


# ---------------------------------------------------------------------------
# Step 5: tangent flow
# ---------------------------------------------------------------------------

def tangent_flow(L_bar: np.ndarray, H: np.ndarray) -> np.ndarray:
    """
    Tangent flow  F = L̅ · H.

    Parameters
    ----------
    L_bar : ndarray, shape (N, N)  — complement Laplacian
    H     : ndarray, shape (N, d)  — hidden states

    Returns
    -------
    F : ndarray, shape (N, d)
    """
    return L_bar @ H


# ---------------------------------------------------------------------------
# Step 6: regression matrix
# ---------------------------------------------------------------------------

def regression_matrix(Theta: np.ndarray, F: np.ndarray) -> np.ndarray:
    """
    Regression matrix  R = Θ @ F.

    Parameters
    ----------
    Theta : ndarray, shape (N, N)  — angular distance matrix
    F     : ndarray, shape (N, d)  — tangent flow

    Returns
    -------
    R : ndarray, shape (N, d)  — direct MLP input for the 8 arms
    """
    return Theta @ F


# ---------------------------------------------------------------------------
# Convenience: run the full pipeline in one call
# ---------------------------------------------------------------------------

def compute_R(
    A: np.ndarray,
    H: np.ndarray,
    tau: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Run all six pipeline steps and return intermediate tensors.

    Parameters
    ----------
    A   : (N, N) adjacency
    H   : (N, d) hidden states
    tau : temperature

    Returns
    -------
    R      : (N, d) regression matrix
    A_bar  : (N, N) complement adjacency
    Theta  : (N, N) angular distance
    F      : (N, d) tangent flow
    """
    A_bar  = complement_graph(A)
    C      = scup_cosine(H, tau)
    Theta  = angular_dist(C)
    L_bar  = complement_laplacian(A_bar)
    F      = tangent_flow(L_bar, H)
    R      = regression_matrix(Theta, F)
    return R, A_bar, Theta, F
