"""
LoRA Sucker — dynamic low-rank adapter that spawns onto a gardening arm.

Each sucker is a rank-r LoRA correction applied additively to an arm's output:

    sucker(R) = (B @ A @ R.T).T  →  (N, D)

Where:
    A ∈ ℝ^(r × D)   — down-projection  (initialized from N(0, 1/r))
    B ∈ ℝ^(D × r)   — up-projection    (initialized to zero, so sucker starts silent)
    scale            — α / r  (LoRA scaling factor, α=1 by default)

Spawn rule:
    if ‖R(u)‖ > spawn_threshold for any node u → SuckerPool.maybe_spawn()
    new sucker optionally inherits A from BERT clipper's projection weights (clipped rows)

SuckerPool holds an unbounded list of LoRASuckers per arm.
The pool's combined correction is the sum of all active sucker outputs.

Parameters per sucker (r=8, D=256):
    A: 8 × 256  = 2048
    B: 256 × 8  = 2048
    Total:       ~4K per sucker   (negligible per spawn)

Reference:
    LoRA: Low-Rank Adaptation of Large Language Models (Hu et al., 2021)
    Applied here to gardening arm outputs, not attention weight matrices.
"""
import math
from typing import List, Optional

try:
    import torch
    import torch.nn as nn
    _TORCH_OK = True
except ImportError:
    torch = None  # type: ignore[assignment]
    nn = None     # type: ignore[assignment]
    _TORCH_OK = False


class LoRASucker(nn.Module):
    """
    Single low-rank sucker attached to one gardening arm.

    Args:
        d_model:     arm hidden dimension (= GNN hidden_dim)
        rank:        LoRA rank r (default 8)
        alpha:       LoRA scaling numerator (scale = alpha / rank)
        init_A:      optional tensor to warm-start A from (BERT clipper projection rows)
    """

    def __init__(
        self,
        d_model: int,
        rank: int = 8,
        alpha: float = 1.0,
        init_A: Optional[torch.Tensor] = None,
    ) -> None:
        super().__init__()
        self.rank = rank
        self.scale = alpha / rank

        self.A = nn.Parameter(torch.empty(rank, d_model))
        self.B = nn.Parameter(torch.zeros(d_model, rank))

        if init_A is not None and init_A.ndim == 2 and init_A.size(1) == d_model:
            # Warm-start A from BERT projection rows (shape must be (≤rank, d_model))
            rows = min(rank, init_A.size(0))
            with torch.no_grad():
                self.A[:rows] = init_A[:rows]
                if rows < rank:
                    nn.init.kaiming_uniform_(self.A[rows:], a=math.sqrt(5))
        else:
            nn.init.kaiming_uniform_(self.A, a=math.sqrt(5))

    def forward(self, R: torch.Tensor) -> torch.Tensor:
        """
        Args:
            R: (N, D) — regression matrix from OctopusTracer

        Returns:
            correction: (N, D) — additive low-rank correction to arm output
        """
        # (N, D) @ (D, r) → (N, r) → (N, r) @ (r, D) ... but B is (D, r)
        # correction = R @ A.T @ B.T = (N, D) @ (D, r) @ (r, D)
        down = R @ self.A.T           # (N, r)
        up   = down @ self.B.T        # (N, D)
        return self.scale * up

    def param_count(self) -> int:
        return sum(p.numel() for p in self.parameters())


class SuckerPool(nn.Module):
    """
    Unbounded pool of LoRASuckers for one gardening arm.

    Suckers spawn when per-node regression pressure exceeds spawn_threshold.
    Each spawned sucker is added to the ModuleList (tracked by PyTorch) and
    contributes additively to the arm's correction signal.

    The pool also tracks which graph region triggered each spawn (spawn_node_idx),
    useful for per-region pressure reporting.

    Args:
        d_model:          GNN hidden dimension
        rank:             LoRA rank for each spawned sucker
        alpha:            LoRA scaling factor
        spawn_threshold:  ‖R(u)‖ floor that triggers a new spawn
    """

    def __init__(
        self,
        d_model: int,
        rank: int = 8,
        alpha: float = 1.0,
        spawn_threshold: float = 1.0,
    ) -> None:
        super().__init__()
        self.d_model = d_model
        self.rank = rank
        self.alpha = alpha
        self.spawn_threshold = spawn_threshold

        self.suckers: nn.ModuleList = nn.ModuleList()
        self._spawn_pressures: List[float] = []   # pressure at time of spawn
        self._spawn_node_idxs: List[int]  = []    # which node triggered

    # ──────────────────────────────────────────────────────────────────────────
    # Spawn
    # ──────────────────────────────────────────────────────────────────────────

    def maybe_spawn(
        self,
        R: torch.Tensor,                          # (N, D)
        bert_proj_weight: Optional[torch.Tensor] = None,  # (out, in) from BERT clipper
    ) -> bool:
        """
        Inspect per-node pressure ‖R(u)‖. If any node exceeds spawn_threshold,
        spawn a new sucker warm-started from bert_proj_weight (if provided).

        Returns True if a sucker was spawned this call.
        """
        pressure = torch.norm(R, dim=-1)          # (N,)
        max_pressure, max_idx = pressure.max(dim=0)

        if max_pressure.item() <= self.spawn_threshold:
            return False

        init_A = None
        if bert_proj_weight is not None:
            weight = bert_proj_weight.detach()
            # Only warm-start when the weight column dim matches d_model exactly.
            # encoder.proj.weight is (out=d_model, in=bert_dim) — transposing as needed.
            if weight.ndim == 2:
                if weight.size(1) == self.d_model and weight.size(0) >= self.rank:
                    # Weight rows are (rank, d_model) compatible
                    init_A = weight[:self.rank].clone()
                elif weight.size(0) == self.d_model and weight.size(1) >= self.rank:
                    # Transposed layout — take columns
                    init_A = weight[:, :self.rank].T.clone()  # (rank, d_model)

        sucker = LoRASucker(
            d_model=self.d_model,
            rank=self.rank,
            alpha=self.alpha,
            init_A=init_A,
        ).to(R.device)

        self.suckers.append(sucker)
        self._spawn_pressures.append(max_pressure.item())
        self._spawn_node_idxs.append(max_idx.item())
        return True

    # ──────────────────────────────────────────────────────────────────────────
    # Forward — sum all active suckers
    # ──────────────────────────────────────────────────────────────────────────

    def forward(self, R: torch.Tensor) -> torch.Tensor:
        """
        Args:
            R: (N, D)

        Returns:
            correction: (N, D)  — summed contribution of all active suckers.
                        Zero tensor if no suckers have spawned yet.
        """
        if len(self.suckers) == 0:
            return torch.zeros_like(R)
        return sum(s(R) for s in self.suckers)

    # ──────────────────────────────────────────────────────────────────────────
    # Inspection
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self.suckers)

    def param_count(self) -> int:
        return sum(p.numel() for s in self.suckers for p in s.parameters())

    def pressure_history(self) -> List[float]:
        return list(self._spawn_pressures)
