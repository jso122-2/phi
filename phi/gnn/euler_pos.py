"""
Euler Walk Position Encoding
Applies Euler rotations e^(i·k·ω) to neighbor embeddings before they enter
the EulerSSM, encoding their position in the neighborhood walk sequence.

This is the graph analogue of Rotary Position Embedding (RoPE):
    - In LLMs: token at position k gets rotated by e^(i·k·ω_d) per dimension pair
    - Here:    neighbor at walk position k gets rotated by e^(i·k·ω_d)

The key property of Euler rotations is that the dot product between two
embeddings depends only on their *relative* walk distance:
    ⟨f(x_j, j), f(x_k, k)⟩ = ⟨x_j, x_k⟩_rotated by (j-k)

So the SSM naturally attends to neighbors based on:
  1. Semantic similarity (embedding content)
  2. Walk-position relationship (topological proximity in traversal order)

Both signals flow through without adding parameters — frequencies ω_d are
fixed geometric progressions (θ_d = base^{-2d/D}), identical to RoPE.

Why Euler's formula specifically:
    e^(iθ) = cos θ + i sin θ
    Acting on a 2D pair (x_{2d}, x_{2d+1}):
    [cos θ  -sin θ] [x_{2d}  ]   =   [x_{2d}·cos θ - x_{2d+1}·sin θ]
    [sin θ   cos θ] [x_{2d+1}]       [x_{2d}·sin θ + x_{2d+1}·cos θ]
    This is a pure rotation — it preserves norm, adds no distortion.

No trainable parameters. Zero budget impact.
"""
import math
from typing import Optional

try:
    import torch
    import torch.nn as nn
    _TORCH_OK = True
except ImportError:
    torch = None  # type: ignore[assignment]
    nn = None     # type: ignore[assignment]
    _TORCH_OK = False


class EulerWalkPositionEncoder(nn.Module):
    """
    Applies Euler phase rotations to an ordered sequence of neighbor embeddings.

    Each position k in [0, max_seq_len) and each dimension pair (2d, 2d+1)
    gets rotated by angle k · θ_d where θ_d = base^(-2d/D).

    Usage:
        encoder = EulerWalkPositionEncoder(hidden_dim=256)
        # x: (batch, seq_len, hidden_dim) — e.g. ordered neighbor embeddings
        x_rotated = encoder(x)

    The rotation is applied in-place — no new dimensions, no projection.
    Works with any sequence length ≤ max_seq_len.

    Args:
        hidden_dim:   feature dimension (must be even)
        max_seq_len:  pre-compute frequencies up to this length
        base:         frequency base (default 10000, same as RoPE)
    """

    def __init__(
        self,
        hidden_dim: int,
        max_seq_len: int = 64,
        base: float = 10000.0,
    ) -> None:
        super().__init__()
        assert hidden_dim % 2 == 0, "hidden_dim must be even for Euler rotation pairs"
        self.hidden_dim = hidden_dim
        self.max_seq_len = max_seq_len

        # Precompute cos/sin tables for all positions and dimension pairs
        # freq_d = base^(-2d/D)  for d = 0, 1, ..., D/2-1
        d = hidden_dim // 2
        freqs = 1.0 / (base ** (torch.arange(0, d, dtype=torch.float) / d))
        # positions k = 0, 1, ..., max_seq_len-1
        t = torch.arange(max_seq_len, dtype=torch.float)
        angles = torch.outer(t, freqs)               # (max_seq_len, d)

        # Register as non-parameter buffers (no gradient, no checkpoint bloat)
        self.register_buffer("cos_table", angles.cos())   # (max_seq_len, d)
        self.register_buffer("sin_table", angles.sin())   # (max_seq_len, d)

    def forward(self, x: torch.Tensor, offset: int = 0) -> torch.Tensor:
        """
        Apply Euler walk position rotations to a batch of sequences.

        Args:
            x:      (..., seq_len, hidden_dim) — neighbor embeddings in walk order
            offset: starting position index (for continuing a sequence)

        Returns:
            x_rot: same shape as x, with Euler-rotated position encoding baked in
        """
        seq_len = x.shape[-2]
        assert seq_len + offset <= self.max_seq_len, (
            f"Sequence length {seq_len}+{offset} exceeds max_seq_len {self.max_seq_len}"
        )

        cos = self.cos_table[offset: offset + seq_len]  # (seq_len, d)
        sin = self.sin_table[offset: offset + seq_len]

        # Split into pairs: x_r (even dims), x_i (odd dims)
        x_r = x[..., 0::2]    # (..., seq_len, d)
        x_i = x[..., 1::2]    # (..., seq_len, d)

        # Euler rotation:  [x_r, x_i] ← [x_r·cos - x_i·sin, x_r·sin + x_i·cos]
        x_rot_r = x_r * cos - x_i * sin
        x_rot_i = x_r * sin + x_i * cos

        # Interleave back: even → x_rot_r, odd → x_rot_i
        x_out = torch.zeros_like(x)
        x_out[..., 0::2] = x_rot_r
        x_out[..., 1::2] = x_rot_i
        return x_out

    def encode_single(self, x: torch.Tensor, position: int) -> torch.Tensor:
        """Apply Euler rotation for a single walk position. x: (..., hidden_dim)."""
        cos = self.cos_table[position]    # (d,)
        sin = self.sin_table[position]

        x_r, x_i = x[..., 0::2], x[..., 1::2]
        x_out = torch.zeros_like(x)
        x_out[..., 0::2] = x_r * cos - x_i * sin
        x_out[..., 1::2] = x_r * sin + x_i * cos
        return x_out

    def visualise_rotation(self, positions: int = 8) -> dict:
        """
        Show what Euler rotation looks like at each walk position.
        Returns angles (in radians) for the first few frequency bands.
        """
        angles = {}
        for k in range(min(positions, self.max_seq_len)):
            band_angles = (
                self.cos_table[k].arccos().cpu().tolist()[:4]   # first 4 freq bands
            )
            angles[f"position_{k}"] = band_angles
        return angles
