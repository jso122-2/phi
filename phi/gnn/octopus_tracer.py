"""
OctopusTracer — Obsidian-bound gardening transformer (≤4M params).

Two operating modes, selected by `soft_edge_mode`:

  SOFT EDGE MODE (default, recommended for autonomous operation)
  ─────────────────────────────────────────────────────────────
  No adjacency matrix required.  R is computed as a soft neighbourhood
  aggregation driven entirely by embedding similarity:

      S[u,v] = sigmoid( (ĥᵤ · ĥᵥ) / τ )     ← soft edge activation
      S.fill_diagonal_(0)                      ← no self-loops
      R = S @ H                                ← (N, D) neighbourhood summary

  High S → nodes are semantically close, R reflects shared context.
  Low S  → isolated node, R has low energy → arm pressure rises.

  FULL REGRESSION MODE (research / ablation)
  ──────────────────────────────────────────
  Requires an adjacency matrix.  Computes:
      R = arccos(scup_cos(H)) @ (L̅ · H)
  as originally designed (complement Laplacian + angular distance).

Both modes feed R → 8 MLP arms → scores.

CAIRRN coupling:
    coherence = exp(−tick / τ_cairrn)   ← matches CAIRRN Layer 3
    coherence < 0.50 → arms read-only, no vault writes

Parameter budget (D=256, K=16, T=64, rank=8):
    8 arm MLPs + log_tau:   ≈ 251K
    LoRA suckers (floor=0):      0  (elastic — unbounded on spawn)
    Total tracer floor:     ≈ 251K   (combined with SambaGNN ≈ 1.2M)

Reference:
    LoRA: Hu et al. (2021)
    Euler SSM backbone: this work (euler_ssm.py)
"""
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

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

from .tracer_arms import (
    PruneArm, GraftArm, ClusterArm, RankArm,
    TagArm, ResurfaceArm, MergeArm, SproutArm,
    ARM_NAMES,
)


# ──────────────────────────────────────────────────────────────────────────────
# Output container
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class TracerOutput:
    """
    Full output of one OctopusTracer forward pass.

    All tensors are on the same device as the input H.
    Pairwise tensors (graft, merge) are upper-triangular.
    """
    prune:     torch.Tensor   # (N,)     — prune score ∈ [0, 1]
    graft:     torch.Tensor   # (N, N)   — link probability on G̅
    cluster:   torch.Tensor   # (N, K)   — soft cluster assignment
    rank:      torch.Tensor   # (N,)     — within-cluster relevance
    tag:       torch.Tensor   # (N, T)   — multi-label tag probability
    resurface: torch.Tensor   # (N,)     — burial score ∈ [0, 1]
    merge:     torch.Tensor   # (N, N)   — near-duplicate probability
    sprout:    torch.Tensor   # (N,)     — structural gap score ∈ [0, 1]

    R: torch.Tensor           # (N, D)   — regression matrix (for inspection)
    coherence_score: float    # scalar   — CAIRRN gate value
    write_gated: bool         # True if coherence ≥ 0.50 (arms have write authority)

    sucker_counts: Dict[str, int] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────────────
# Main model
# ──────────────────────────────────────────────────────────────────────────────

class OctopusTracer(nn.Module):
    """
    Obsidian-bound gardening transformer that spawns on vault graph conditions
    and autonomously prunes, grafts, clusters, ranks, tags, resurfaces, merges,
    and sprouts nodes — all in sync with CAIRRN tick cycles.

    Args:
        d_model:          GNN hidden dimension (must match SambaGNN hidden_dim)
        num_clusters:     number of gardening clusters (Arm 3)
        num_tags:         tag vocabulary size (Arm 5)
        lora_rank:        LoRA rank for all SuckerPools
        spawn_threshold:  ‖R(u)‖ threshold that triggers a new sucker spawn
        tau_cairrn:       CAIRRN coherence time constant (default 30 steps)
        scup_temp:        initial scup cosine temperature τ (learnable)
    """

    def __init__(
        self,
        d_model: int = 256,
        num_clusters: int = 16,
        num_tags: int = 64,
        lora_rank: int = 8,
        spawn_threshold: float = 1.0,
        tau_cairrn: float = 30.0,
        scup_temp: float = 1.0,
        soft_edge_mode: bool = True,
    ) -> None:
        super().__init__()
        self.d_model = d_model
        self.tau_cairrn = tau_cairrn
        self.soft_edge_mode = soft_edge_mode

        # ── Scup cosine temperature (learnable scalar) ────────────────────────
        # Initialised to scup_temp; updated by BERT clipper's τ via inject_temperature()
        self.log_tau = nn.Parameter(torch.tensor(math.log(scup_temp)))

        # ── 8 Gardening arms ─────────────────────────────────────────────────
        kw = dict(d_model=d_model, rank=lora_rank, spawn_threshold=spawn_threshold)
        self.arm_prune     = PruneArm(**kw)
        self.arm_graft     = GraftArm(**kw)
        self.arm_cluster   = ClusterArm(d_model=d_model, num_clusters=num_clusters,
                                        rank=lora_rank, spawn_threshold=spawn_threshold)
        self.arm_rank      = RankArm(**kw)
        self.arm_tag       = TagArm(d_model=d_model, num_tags=num_tags,
                                    rank=lora_rank, spawn_threshold=spawn_threshold)
        self.arm_resurface = ResurfaceArm(**kw)
        self.arm_merge     = MergeArm(**kw)
        self.arm_sprout    = SproutArm(**kw)

        self._arms = {
            "prune":     self.arm_prune,
            "graft":     self.arm_graft,
            "cluster":   self.arm_cluster,
            "rank":      self.arm_rank,
            "tag":       self.arm_tag,
            "resurface": self.arm_resurface,
            "merge":     self.arm_merge,
            "sprout":    self.arm_sprout,
        }

        # ── CAIRRN tick counter ───────────────────────────────────────────────
        self._tick: int = 0

    # ──────────────────────────────────────────────────────────────────────────
    # R pipeline — two modes
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def tau(self) -> torch.Tensor:
        """Soft edge / scup temperature: exp(log_tau) > 0, learnable."""
        return self.log_tau.exp()

    def _scup_cosine(self, H: torch.Tensor) -> torch.Tensor:
        """Scup cosine for full regression mode. Clamped for arccos stability."""
        H_norm = F.normalize(H, dim=-1)
        C = (H_norm @ H_norm.T) / self.tau
        return C.clamp(-1.0 + 1e-6, 1.0 - 1e-6)

    def _regression_pipeline(
        self,
        H: torch.Tensor,
        adj: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Full regression pipeline returning (R, A_bar).

        A_bar — the complement adjacency — is returned alongside R so that
        OctopusAttentionHead in each arm can use it directly as the locked
        architecture specifies: 'Ā̅ is the direct MLP input.'

        Soft edge mode (adj not required):
            S[u,v] = sigmoid((ĥᵤ·ĥᵥ) / τ),  S.diag = 0
            R     = S @ H                          ← (N, D) neighbourhood summary
            A_bar = (1 − S) with diagonal zeroed   ← soft complement ∈ (0, 1)^(N×N)

        Full regression mode (requires adj):
            C     = scup_cos(H)
            Θ     = arccos(C)
            A_bar = complement of adj              ← hard {0,1} complement
            L̅    = D̅ − A_bar
            F     = L̅ · H
            R     = Θ @ F
        """
        N   = H.size(0)
        eye = torch.eye(N, device=H.device, dtype=H.dtype)

        if self.soft_edge_mode:
            H_norm = F.normalize(H, dim=-1)
            raw    = (H_norm @ H_norm.T) / self.tau
            S      = torch.sigmoid(raw) * (1 - eye)
            R      = S @ H
            A_bar  = (1 - S - eye).clamp(min=0.0)
            return R, A_bar

        assert adj is not None, "adj required when soft_edge_mode=False"
        A     = (adj > 0).float()
        A.fill_diagonal_(0.0)
        ones  = torch.ones(N, N, device=H.device, dtype=H.dtype)
        A_bar = (ones - eye - A).clamp(min=0.0)
        D_bar = torch.diag(A_bar.sum(dim=-1))
        L_bar = D_bar - A_bar

        C     = self._scup_cosine(H)
        Theta = torch.acos(C)
        Fmat  = L_bar @ H
        R     = Theta @ Fmat
        return R, A_bar

    # ──────────────────────────────────────────────────────────────────────────
    # CAIRRN coherence gate
    # ──────────────────────────────────────────────────────────────────────────

    def tick(self) -> None:
        """Advance the CAIRRN tick counter by one step."""
        self._tick += 1

    def reset_tick(self) -> None:
        """Reset tick counter (called when tracer coherence is re-established)."""
        self._tick = 0

    @property
    def coherence_score(self) -> float:
        """
        CAIRRN coherence gate value: exp(−steps / τ_cairrn).
        Matches Layer 3 of the CAIRRN pipeline.
        """
        return math.exp(-self._tick / self.tau_cairrn)

    @property
    def write_gated(self) -> bool:
        """True when coherence ≥ 0.50 — arms have write authority."""
        return self.coherence_score >= 0.50

    # ──────────────────────────────────────────────────────────────────────────
    # Sucker management
    # ──────────────────────────────────────────────────────────────────────────

    def maybe_spawn_suckers(
        self,
        R: torch.Tensor,
        bert_proj_weight: Optional[torch.Tensor] = None,
    ) -> Dict[str, bool]:
        """
        Offer R to each arm's SuckerPool. Returns dict of {arm_name: spawned}.
        """
        spawned = {}
        for name, arm in self._arms.items():
            spawned[name] = arm.maybe_spawn_sucker(R, bert_proj_weight)
        return spawned

    def inject_temperature(self, tau: float) -> None:
        """Override scup temperature from BERT clipper's live τ."""
        with torch.no_grad():
            self.log_tau.fill_(math.log(max(tau, 1e-6)))

    # ──────────────────────────────────────────────────────────────────────────
    # Forward
    # ──────────────────────────────────────────────────────────────────────────

    def forward(
        self,
        H: torch.Tensor,                                    # (N, D) node embeddings
        adj: Optional[torch.Tensor] = None,                 # (N, N) — only needed in full regression mode
        existing_edge_mask: Optional[torch.Tensor] = None,  # (N, N) bool — suppress Graft
        bert_proj_weight: Optional[torch.Tensor]  = None,   # for sucker warm-start
        auto_spawn: bool = True,
    ) -> TracerOutput:
        """
        Full octopus tracer forward pass.

        In soft_edge_mode (default) `adj` is not required — the tracer is fully
        autonomous from node embeddings H alone.

        Args:
            H:                   (N, D) node embeddings (output of SambaGNN)
            adj:                 (N, N) adjacency — only needed when soft_edge_mode=False
            existing_edge_mask:  (N, N) bool — suppress known edges for Graft arm.
                                 In soft_edge_mode, auto-derived from high-S pairs if None.
            bert_proj_weight:    BERT proj weight for sucker warm-start
            auto_spawn:          check for sucker spawns after computing R

        Returns:
            TracerOutput with all 8 arm outputs + R + coherence metadata
        """
        assert H.ndim == 2 and H.size(-1) == self.d_model, \
            f"Expected H (N, {self.d_model}), got {tuple(H.shape)}"

        # ── Regression pipeline — returns R and Ā̅ ─────────────────────────────
        R, A_bar = self._regression_pipeline(H, adj)   # (N, D), (N, N)

        # ── Graft mask: suppress already-linked pairs ─────────────────────────
        # In soft mode, A_bar = (1 − S) so high-S pairs have low A_bar.
        # We derive the graft mask from A_bar directly (no redundant S recompute).
        graft_mask = existing_edge_mask
        if graft_mask is None and self.soft_edge_mode:
            # A_bar[u,v] < 0.15  ≡  S[u,v] > 0.85 — treat as already linked
            graft_mask = A_bar < 0.15

        # ── Optionally spawn new suckers ──────────────────────────────────────
        if auto_spawn:
            self.maybe_spawn_suckers(R, bert_proj_weight)

        # ── 8 arms — all receive A_bar for the attention head ─────────────────
        prune     = self.arm_prune(R,     A_bar=A_bar)
        graft     = self.arm_graft(R,     mask=graft_mask, A_bar=A_bar)
        cluster   = self.arm_cluster(R,   A_bar=A_bar)
        rank      = self.arm_rank(R,      A_bar=A_bar)
        tag       = self.arm_tag(R,       A_bar=A_bar)
        resurface = self.arm_resurface(R, A_bar=A_bar)
        merge     = self.arm_merge(R,     A_bar=A_bar)
        sprout    = self.arm_sprout(R,    A_bar=A_bar)

        sucker_counts = {name: arm.suckers.count for name, arm in self._arms.items()}

        return TracerOutput(
            prune=prune,
            graft=graft,
            cluster=cluster,
            rank=rank,
            tag=tag,
            resurface=resurface,
            merge=merge,
            sprout=sprout,
            R=R,
            coherence_score=self.coherence_score,
            write_gated=self.write_gated,
            sucker_counts=sucker_counts,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Inspection
    # ──────────────────────────────────────────────────────────────────────────

    def parameter_report(self) -> Dict[str, int]:
        def count(m: nn.Module) -> int:
            return sum(p.numel() for p in m.parameters() if p.requires_grad)

        report = {}
        for name, arm in self._arms.items():
            arm_own   = count(arm) - count(arm.suckers)
            arm_suck  = count(arm.suckers)
            report[f"arm_{name}_mlp"]    = arm_own
            report[f"arm_{name}_suckers"] = arm_suck

        report["log_tau"] = 1
        report["total_tracer"] = count(self)
        return report

    def sucker_report(self) -> Dict[str, int]:
        return {name: arm.suckers.count for name, arm in self._arms.items()}
