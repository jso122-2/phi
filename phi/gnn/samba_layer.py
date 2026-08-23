"""
Samba SSM Layer for Graph Message Passing
Implements Euler SSM dynamics as the aggregation operator over an ordered
sequence of neighbor embeddings.

Key insight: instead of permutation-invariant mean/sum pooling, we order the
neighborhood and run an EulerSSM through it — giving the layer oscillatory
memory of traversal, parameterized via Euler's formula e^(iθ).

"Roving weights" = the EulerSSM instance is shared across all GNN layers,
so the same Euler dynamics rove the entire graph depth.

Walk position encoding via EulerWalkPositionEncoder encodes each neighbor's
walk position as a Euler phase rotation before it enters the SSM.

Reference: Mamba (Gu & Dao 2023), S4 (Gu et al. 2022), RoPE (Su et al. 2021),
           adapted for graph neighborhoods with Euler complex parameterization.
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
from einops import rearrange
from typing import Optional


class SelectiveSSM(nn.Module):
    """
    Discrete-time selective state space model.
    Parameters B, C, and delta are input-dependent (selective).
    A is input-independent but learned (log-parameterized for stability).

    Dimensions:
        d_model: input/output feature dim
        d_state: SSM state dimension N
        d_conv:  local depthwise conv kernel size (before SSM)
    """

    def __init__(self, d_model: int, d_state: int = 64, d_conv: int = 4) -> None:
        super().__init__()
        self.d_model = d_model
        self.d_state = d_state
        self.d_conv = d_conv
        self.d_inner = d_model  # no expand here; expansion is in SambaSSMLayer

        # input projection splits into x and z (gating)
        self.in_proj = nn.Linear(d_model, 2 * self.d_inner, bias=False)

        # depthwise conv along the sequence (neighborhood walk) axis
        self.conv1d = nn.Conv1d(
            in_channels=self.d_inner,
            out_channels=self.d_inner,
            kernel_size=d_conv,
            padding=d_conv - 1,
            groups=self.d_inner,
            bias=True,
        )

        # selective projections: B, C, delta — all input-dependent
        self.x_proj = nn.Linear(self.d_inner, d_state + d_state + 1, bias=False)
        self.dt_proj = nn.Linear(1, self.d_inner, bias=True)

        # A: log-domain real diagonal, shape (d_inner, d_state)
        A = torch.arange(1, d_state + 1, dtype=torch.float32).unsqueeze(0)
        A = A.expand(self.d_inner, -1)
        self.A_log = nn.Parameter(torch.log(A))

        # D: skip connection scalar per channel
        self.D = nn.Parameter(torch.ones(self.d_inner))

        self.out_proj = nn.Linear(self.d_inner, d_model, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch, seq_len, d_model)  seq_len = ordered neighborhood size

        Returns:
            y: (batch, seq_len, d_model)
        """
        B, L, _ = x.shape

        xz = self.in_proj(x)                        # (B, L, 2*d_inner)
        x_in, z = xz.chunk(2, dim=-1)              # each (B, L, d_inner)

        # depthwise conv over sequence axis
        x_conv = rearrange(x_in, "b l d -> b d l")
        x_conv = self.conv1d(x_conv)[..., :L]       # causal: drop right padding
        x_conv = rearrange(x_conv, "b d l -> b l d")
        x_conv = F.silu(x_conv)

        # selective params
        xbc_dt = self.x_proj(x_conv)               # (B, L, N+N+1)
        B_sel = xbc_dt[..., :self.d_state]          # (B, L, N)
        C_sel = xbc_dt[..., self.d_state:2*self.d_state]
        dt_raw = xbc_dt[..., -1:]                   # (B, L, 1)
        dt = F.softplus(self.dt_proj(dt_raw))       # (B, L, d_inner)

        A = -torch.exp(self.A_log)                  # (d_inner, N) — negative real

        # discretize A and B with ZOH
        dA = torch.exp(dt.unsqueeze(-1) * A)        # (B, L, d_inner, N)
        dB = dt.unsqueeze(-1) * B_sel.unsqueeze(2)  # (B, L, d_inner, N)

        # scan over sequence
        ys = []
        h = torch.zeros(B, self.d_inner, self.d_state, device=x.device, dtype=x.dtype)
        for t in range(L):
            h = dA[:, t] * h + dB[:, t] * x_conv[:, t].unsqueeze(-1)
            # h: (B, d_inner, N), C_sel: (B, N)
            y_t = (h * C_sel[:, t].unsqueeze(1)).sum(dim=-1)  # (B, d_inner)
            ys.append(y_t)
        y = torch.stack(ys, dim=1)                  # (B, L, d_inner)

        # gated output
        y = y * F.silu(z)
        y = y + x_conv * self.D.unsqueeze(0).unsqueeze(0)  # skip
        return self.out_proj(y)


class SambaSSMLayer(nn.Module):
    """
    One Samba GNN message-passing layer with Euler walk position encoding.

    For each node:
      1. Fetch ordered sequence of neighbor embeddings (walk ordering in utils/walk.py)
      2. Apply EulerWalkPositionEncoder to encode walk position as e^(i·k·ω) rotation
      3. Prepend self-node as causal anchor at position 0
      4. Run EulerSSM over the position-encoded sequence
      5. Aggregate via mean of valid positions (captures full walk memory)
      6. Residual add + layer-norm

    The EulerSSM instance is passed in (not created here) so that the
    same Euler dynamics rove across all GNN layers — the "roving" property.
    The EulerWalkPositionEncoder is also shared (no params, just a frequency table).
    """

    def __init__(
        self,
        hidden_dim: int,
        ssm,    # EulerSSM — typed loosely to avoid circular import
        edge_dim: int = 32,
        dropout: float = 0.1,
        max_seq_len: int = 64,
    ) -> None:
        super().__init__()
        self.ssm = ssm  # shared EulerSSM — same object across all GNN layers

        # Euler walk position encoder (no trainable params)
        from .euler_pos import EulerWalkPositionEncoder
        self.euler_pos = EulerWalkPositionEncoder(
            hidden_dim=hidden_dim,
            max_seq_len=max_seq_len,
        )
        self.norm1 = nn.LayerNorm(hidden_dim)
        self.norm2 = nn.LayerNorm(hidden_dim)
        self.dropout = nn.Dropout(dropout)

        # lightweight edge-conditioned gate: edge type modulates aggregation weight
        self.edge_gate = nn.Sequential(
            nn.Linear(edge_dim, hidden_dim),
            nn.Sigmoid(),
        )

        # post-aggregation feed-forward
        self.ff = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim * 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim * 2, hidden_dim),
        )

    def forward(
        self,
        node_emb: torch.Tensor,          # (N_nodes, hidden_dim)
        neighbor_seqs: torch.Tensor,     # (N_nodes, max_neighbors, hidden_dim) — ordered walk
        edge_feats: torch.Tensor,        # (N_nodes, max_neighbors, edge_dim)
        neighbor_mask: torch.Tensor,     # (N_nodes, max_neighbors) bool — valid neighbors
    ) -> torch.Tensor:
        """
        Returns updated node embeddings of shape (N_nodes, hidden_dim).
        """
        N = node_emb.size(0)

        # gate neighbor features by edge type
        gate = self.edge_gate(edge_feats)           # (N, max_neighbors, hidden_dim)
        gated_seq = neighbor_seqs * gate

        # ── Apply Euler walk position encoding to neighbor sequence ────────
        # Before entering the SSM, each neighbor at walk position k gets
        # rotated by e^(i·k·ω) — encoding its topological walk distance.
        # Position 0 reserved for self-node (added below), so neighbors start at 1.
        gated_seq = self.euler_pos(gated_seq, offset=1)   # (N, max_neighbors, H)

        # prepend self-node as causal anchor at position 0 (no rotation for self)
        self_expanded = node_emb.unsqueeze(1)       # (N, 1, hidden_dim)
        seq = torch.cat([self_expanded, gated_seq], dim=1)   # (N, 1+max_neighbors, H)

        # zero-out padding positions
        pad_mask = torch.cat(
            [torch.ones(N, 1, dtype=torch.bool, device=node_emb.device), neighbor_mask],
            dim=1,
        )  # (N, 1+max_neighbors)
        seq = seq * pad_mask.unsqueeze(-1).float()

        # ── EulerSSM over Euler-position-encoded neighborhood ─────────────
        # The SSM now sees: self-node (anchor) → neighbor_1@pos1 → ... → neighbor_k@posk
        # Each position encoded as a rotation in Euler's complex plane.
        ssm_out = self.ssm(seq)                     # (N, 1+max_neighbors, hidden_dim)

        # aggregate: last valid position captures full walk memory
        # use mean of valid positions (more stable than just last for variable-length)
        valid_counts = pad_mask.float().sum(dim=1, keepdim=True).unsqueeze(-1)  # (N,1,1)
        agg = (ssm_out * pad_mask.unsqueeze(-1).float()).sum(dim=1) / valid_counts.squeeze(1)

        # residual + norm
        h = self.norm1(node_emb + self.dropout(agg))
        h = self.norm2(h + self.dropout(self.ff(h)))
        return h
