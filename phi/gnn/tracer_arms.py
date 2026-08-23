"""
Octopus Tracer — 8 Gardening Arms (MLP task heads).

All arms share the same input: R ∈ ℝ^(N × D)
The regression matrix R is computed upstream by OctopusTracer:
    R = arccos(scup_cos(H)) @ (L̅ · H)

where:
    H   = node embeddings from SambaGNN  (N, D)
    L̅   = complement graph Laplacian     (N, N)

Each arm is a 2-layer MLP preceded by an OctopusAttentionHead.
The attention head implements the locked formula:

    v_d  = β̂(R) × ‖R(u)‖               ← direction beta × drift derivative
    A_vd = Ā̅ × v_d                       ← scaled complement adjacency
    attn = softmax(A_vd @ Ā̅ᵀ − fs, dim=−1)  ← complement-guided attention
    R'   = attn @ R                       ← attended regression (MLP input)

where fs ∈ (0, 24) — the fixed set, bounded by 23.999̄ = 24.

Arm output shapes:

    1. Prune      →  (N,)       [0,1] score  — 1 = delete candidate
    2. Graft      →  (N, N)     [0,1] matrix — upper-tri link probability on G̅
    3. Cluster    →  (N, K)     softmax      — cluster reassignment
    4. Rank       →  (N,)       float        — within-cluster relevance score
    5. Tag        →  (N, T)     sigmoid      — per-tag probability
    6. Resurface  →  (N,)       [0,1] score  — 1 = deeply buried, needs surfacing
    7. Merge      →  (N, N)     [0,1] matrix — upper-tri near-duplicate probability
    8. Sprout     →  (N,)       [0,1] score  — structural gap magnitude at node u

Arms 2 (Graft) and 7 (Merge) are pairwise: they project R' → P then score P @ Pᵀ.
Arms 1, 4, 6, 8 are scalar scorers.
Arm 3 (Cluster) replaces the old ClusterHead for gardening context.
Arm 5 (Tag) uses a configurable tag vocabulary size.

Parameter budget (D=256, K=16, T=64):
    Attention heads ×8: 8 × (256 + 1)             ≈    2K
    Scalar arms ×4:     4 × (256×128 + 128×1)      ≈  132K
    Pairwise arms ×2:   2 × (256×128)              ≈   66K
    Cluster arm:        256×16                     ≈    4K
    Rank arm:           256×128 + 128×1            ≈   33K
    Tag arm:            256×64                     ≈   16K
    ──────────────────────────────────────────────────────
    Total:                                         ≈  253K
"""
import math
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    _TORCH_OK = True
except ImportError:
    torch = None  # type: ignore[assignment]
    nn = None     # type: ignore[assignment]
    F = None      # type: ignore[assignment]
    _TORCH_OK = False
from typing import Optional

from .lora_sucker import SuckerPool


# ──────────────────────────────────────────────────────────────────────────────
# Attention head — locked formula
# ──────────────────────────────────────────────────────────────────────────────

class OctopusAttentionHead(nn.Module):
    """
    Complement-adjacency attention head (architecture-locked).

    Implements:
        v_d  = β̂(R) × ‖R(u)‖               # (N,) direction beta × drift
        A_vd = Ā̅ × diag(v_d)               # (N, N) column-scaled complement
        attn = softmax(A_vd @ Ā̅ᵀ − fs, dim=−1)  # (N, N) attention weights
        R'   = attn @ R                      # (N, D) attended regression

    The fixed set fs ∈ (0, 24) is a per-arm learnable scalar, strictly bounded
    below 23.999̄ = 24 via sigmoid gating:
        fs = 24 × σ(raw)

    For graphs with N > max_n, falls back to linear per-node weighting (O(ND)
    instead of O(N²D)) to keep memory bounded on large vaults:
        scores = Ā̅ @ v_d − fs        # (N,)
        attn   = softmax(scores, 0)   # (N,)
        R'     = attn.unsqueeze(−1) × R

    Args:
        d_model: embedding dimension (= R.shape[−1])
        max_n:   maximum N for full O(N²) attention (default 2048)
    """

    _FS_MAX: float = 24.0           # 23.999̄ = 24, the fixed-set ceiling

    def __init__(self, d_model: int, max_n: int = 2048) -> None:
        super().__init__()
        self.d_model = d_model
        self.max_n   = max_n

        # β̂: direction projection R → per-node scalar
        self.beta_proj = nn.Linear(d_model, 1, bias=False)
        nn.init.kaiming_uniform_(self.beta_proj.weight, a=0.01)

        # fs raw parameter — sigmoid-gated to (0, 24)
        self._fs_raw = nn.Parameter(torch.zeros(1))

    @property
    def fs(self) -> torch.Tensor:
        """Fixed set: 24 × σ(raw) ∈ (0, 24). Strictly bounded below 23.999̄."""
        return self._FS_MAX * torch.sigmoid(self._fs_raw)

    def forward(
        self,
        R: torch.Tensor,        # (N, D) regression matrix
        A_bar: torch.Tensor,    # (N, N) complement adjacency
    ) -> torch.Tensor:
        """
        Args:
            R:     (N, D) regression matrix from the regression pipeline
            A_bar: (N, N) complement adjacency (soft or hard)

        Returns:
            R_attended: (N, D) complement-attended regression matrix
        """
        N = R.size(0)

        # direction beta × drift derivative
        beta  = self.beta_proj(R).squeeze(-1)   # (N,)
        drift = R.norm(dim=-1)                   # (N,) — ‖R(u)‖
        v_d   = beta * drift                     # (N,)

        if N <= self.max_n:
            # Full O(N²) bilinear complement-adjacency attention
            #
            #   A_vd[u, k] = Ā̅[u, k] × v_d[k]           (scale columns by v_d)
            #   logit[u, v] = Σ_k A_vd[u,k] × Ā̅[v,k]   = A_vd @ Ā̅ᵀ
            #   attn         = softmax(logit − fs, dim=−1)
            #
            A_vd   = A_bar * v_d.unsqueeze(0)              # (N, N)
            logits = A_vd @ A_bar.t() - self.fs            # (N, N)
            attn   = torch.softmax(logits, dim=-1)          # (N, N)
            return attn @ R                                 # (N, D)
        else:
            # Linear fallback: per-node weighting via complement dot-product
            #   score[u] = Ā̅[u] · v_d − fs
            scores = (A_bar @ v_d.unsqueeze(-1)).squeeze(-1) - self.fs  # (N,)
            attn   = torch.softmax(scores, dim=0)           # (N,)
            return attn.unsqueeze(-1) * R                   # (N, D)


# ──────────────────────────────────────────────────────────────────────────────
# Base
# ──────────────────────────────────────────────────────────────────────────────

class GardeningArm(nn.Module):
    """
    Abstract base for all 8 arms.

    Each arm owns:
      - an OctopusAttentionHead  (complement-adjacency preprocessing)
      - a SuckerPool             (elastic LoRA correction)

    The attention head transforms R → R' using Ā̅ before the arm's MLP.
    The sucker correction is applied to R' additively.

    Args:
        d_model:          GNN hidden dimension (= R.shape[-1])
        rank:             LoRA rank for suckers
        spawn_threshold:  ‖R(u)‖ floor for sucker spawn
        max_n:            N threshold for full vs linear attention
    """

    def __init__(
        self,
        d_model: int,
        rank: int = 8,
        spawn_threshold: float = 1.0,
        max_n: int = 2048,
    ) -> None:
        super().__init__()
        self.d_model  = d_model
        self.attn_head = OctopusAttentionHead(d_model, max_n=max_n)
        self.suckers   = SuckerPool(
            d_model=d_model,
            rank=rank,
            spawn_threshold=spawn_threshold,
        )

    def attend(
        self,
        R: torch.Tensor,
        A_bar: Optional[torch.Tensor],
    ) -> torch.Tensor:
        """
        Apply the OctopusAttentionHead when A_bar is available,
        otherwise pass R through unchanged (soft-edge fallback).
        """
        if A_bar is not None:
            return self.attn_head(R, A_bar)
        return R

    def maybe_spawn_sucker(
        self,
        R: torch.Tensor,
        bert_proj_weight: Optional[torch.Tensor] = None,
    ) -> bool:
        return self.suckers.maybe_spawn(R, bert_proj_weight)

    def sucker_correction(self, R: torch.Tensor) -> torch.Tensor:
        """(N, D) additive correction from all active suckers."""
        return self.suckers(R)


# ──────────────────────────────────────────────────────────────────────────────
# Scalar arms  (output: (N,))
# ──────────────────────────────────────────────────────────────────────────────

class _ScalarArm(GardeningArm):
    """Shared implementation for arms that score each node independently."""

    def __init__(
        self,
        d_model: int,
        rank: int = 8,
        spawn_threshold: float = 1.0,
        max_n: int = 2048,
    ) -> None:
        super().__init__(d_model, rank, spawn_threshold, max_n)
        half = d_model // 2
        self.mlp = nn.Sequential(
            nn.Linear(d_model, half),
            nn.GELU(),
            nn.Linear(half, 1),
        )

    def forward(
        self,
        R: torch.Tensor,
        A_bar: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Args:
            R:     (N, D) regression matrix
            A_bar: (N, N) complement adjacency — activates attention head

        Returns:
            scores: (N,) ∈ [0, 1]

        R_att can collapse toward mean(R) when N is large and A_bar is dense.
        Adding the original R as a skip ensures each node's own representation
        always reaches the MLP regardless of attention quality.
        """
        R_att = self.attend(R, A_bar)
        R_aug = R + R_att + self.sucker_correction(R_att)   # skip: node + context + sucker
        return torch.sigmoid(self.mlp(R_aug).squeeze(-1))


class PruneArm(_ScalarArm):
    """
    Arm 1 — Prune.
    Scores each node for deletion candidacy.
    High score → orphan / stale / duplicate — flag for removal.

    Input:  R (N, D)
    Output: prune_score (N,) ∈ [0, 1]
    """


class RankArm(_ScalarArm):
    """
    Arm 4 — Rank.
    Assigns within-cluster relevance score.
    High score → most central / coherent node in its neighbourhood.

    Input:  R (N, D)
    Output: rank_score (N,) ∈ [0, 1]
    """


class ResurfaceArm(_ScalarArm):
    """
    Arm 6 — Resurface.
    Detects deeply buried high-value nodes.
    High score → node is semantically rich but structurally peripheral.

    Input:  R (N, D)
    Output: burial_score (N,) ∈ [0, 1]
    """


class SproutArm(_ScalarArm):
    """
    Arm 8 — Sprout.
    Detects structural gaps where new connective tissue should be created.
    High score → this node's neighbourhood is sparse and semantically underrepresented.

    Input:  R (N, D)
    Output: gap_score (N,) ∈ [0, 1]
    """


# ──────────────────────────────────────────────────────────────────────────────
# Pairwise arms  (output: (N, N))
# ──────────────────────────────────────────────────────────────────────────────

class _PairwiseArm(GardeningArm):
    """
    Shared implementation for arms that score node pairs.

    Projects R' into a comparison space, L2-normalises to the unit sphere,
    then scores all pairs via scaled cosine similarity:

        P_norm = L2_norm(proj(R'))        # (N, D//2) — unit vectors
        logits  = P_norm @ P_normᵀ / τ   # (N, N) ∈ [-1/τ, 1/τ]
        scores  = sigmoid(logits)         # (N, N) ∈ (0, 1)

    The learnable temperature τ = exp(log_temp) starts at 1.0.  Because
    P_norm is L2-normalised, dot products are bounded to [-1, 1] regardless
    of N or embedding magnitude — the score distribution is N-stable.
    Without normalisation, raw dot products grow with ‖P‖² and the count of
    edges above any fixed threshold flips wildly when N changes.
    """

    def __init__(
        self,
        d_model: int,
        rank: int = 8,
        spawn_threshold: float = 1.0,
        max_n: int = 2048,
    ) -> None:
        super().__init__(d_model, rank, spawn_threshold, max_n)
        self.proj = nn.Linear(d_model, d_model // 2, bias=False)
        # Learnable temperature: τ = exp(log_temp), init τ = 1.0
        self.log_temp = nn.Parameter(torch.zeros(1))

    @property
    def temp(self) -> torch.Tensor:
        """Pairwise temperature τ ∈ (0, ∞). Clamped to ≥ 0.05 for stability."""
        return self.log_temp.exp().clamp(min=0.05)

    def forward(
        self,
        R: torch.Tensor,                          # (N, D)
        mask: Optional[torch.Tensor] = None,      # (N, N) bool — True = suppress
        A_bar: Optional[torch.Tensor] = None,     # (N, N) complement adjacency
    ) -> torch.Tensor:
        """
        Args:
            R:     (N, D) regression matrix
            mask:  (N, N) bool — positions to zero out
            A_bar: (N, N) complement adjacency — activates attention head

        Returns:
            pair_scores: (N, N) ∈ (0, 1), upper-triangular
        """
        R_att = self.attend(R, A_bar)
        R_aug = R + R_att + self.sucker_correction(R_att)   # skip: node + context + sucker
        P      = self.proj(R_aug)                            # (N, D//2)
        P_norm = F.normalize(P, dim=-1)                      # unit vectors — N-stable
        logits = P_norm @ P_norm.T / self.temp               # (N, N) ∈ [-1/τ, 1/τ]
        scores = torch.sigmoid(logits)                       # (N, N) ∈ (0, 1)

        N = R.size(0)
        scores = scores * (1 - torch.eye(N, device=scores.device))
        triu_mask = torch.triu(
            torch.ones(N, N, device=scores.device, dtype=torch.bool), diagonal=1
        )
        scores = scores * triu_mask

        if mask is not None:
            scores = scores.masked_fill(mask, 0.0)

        return scores


class GraftArm(_PairwiseArm):
    """
    Arm 2 — Graft.
    Predicts missing links: node pairs in G̅ (complement) that should exist in G.
    High score → missing edge that would improve graph coherence.

    Input:  R (N, D), mask of existing edges
    Output: link_prob (N, N) — upper-tri, [0, 1]
    """


class MergeArm(_PairwiseArm):
    """
    Arm 7 — Merge.
    Identifies near-duplicate note pairs.
    High score → pair should be consolidated (emits candidates only, no autonomous write).

    Input:  R (N, D)
    Output: merge_prob (N, N) — upper-tri, [0, 1]
    """


# ──────────────────────────────────────────────────────────────────────────────
# Cluster arm  (output: (N, K))
# ──────────────────────────────────────────────────────────────────────────────

class ClusterArm(GardeningArm):
    """
    Arm 3 — Cluster.
    Soft cluster reassignment for nodes that have drifted from their neighbourhood.

    Temperature-scaled softmax prevents mode collapse.  log_temp is initialised
    to log(10) so τ = 10 at startup — logits are divided by 10, making the
    initial distribution near-uniform across all K clusters.  As training proceeds,
    τ decreases toward sharper assignments naturally.

    Input:  R (N, D), A_bar (N, N)
    Output: cluster_probs (N, K) — softmax over K clusters
    """

    def __init__(
        self,
        d_model: int,
        num_clusters: int = 16,
        rank: int = 8,
        spawn_threshold: float = 1.0,
        max_n: int = 2048,
    ) -> None:
        super().__init__(d_model, rank, spawn_threshold, max_n)
        self.num_clusters = num_clusters
        self.proj = nn.Linear(d_model, num_clusters)
        # Start diffuse (τ=10), let training sharpen assignments organically
        self.log_temp = nn.Parameter(torch.tensor(math.log(10.0)))

    @property
    def temp(self) -> torch.Tensor:
        """Cluster temperature τ ≥ 0.1."""
        return self.log_temp.exp().clamp(min=0.1)

    def forward(
        self,
        R: torch.Tensor,
        A_bar: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        R_att  = self.attend(R, A_bar)
        R_aug  = R + R_att + self.sucker_correction(R_att)   # skip: node + context + sucker
        logits = self.proj(R_aug)                            # (N, K)
        return F.softmax(logits / self.temp, dim=-1)


# ──────────────────────────────────────────────────────────────────────────────
# Tag arm  (output: (N, T))
# ──────────────────────────────────────────────────────────────────────────────

class TagArm(GardeningArm):
    """
    Arm 5 — Tag.
    Multi-label tag inference: assigns / removes tags per node.

    Input:  R (N, D), A_bar (N, N)
    Output: tag_probs (N, T) — sigmoid, independent per tag
    """

    def __init__(
        self,
        d_model: int,
        num_tags: int = 64,
        rank: int = 8,
        spawn_threshold: float = 1.0,
        max_n: int = 2048,
    ) -> None:
        super().__init__(d_model, rank, spawn_threshold, max_n)
        self.num_tags = num_tags
        self.proj = nn.Linear(d_model, num_tags)

    def forward(
        self,
        R: torch.Tensor,
        A_bar: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        R_att = self.attend(R, A_bar)
        R_aug = R + R_att + self.sucker_correction(R_att)   # skip: node + context + sucker
        return torch.sigmoid(self.proj(R_aug))


# ──────────────────────────────────────────────────────────────────────────────
# Arm registry — named access for CoherenceDaemon
# ──────────────────────────────────────────────────────────────────────────────

ARM_NAMES = ["prune", "graft", "cluster", "rank", "tag", "resurface", "merge", "sprout"]
