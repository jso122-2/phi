"""
EulerSSM — Complex Euler State Space Model

Replaces the real-diagonal A matrix of SelectiveSSM with complex eigenvalues
parameterized via Euler's formula:

    A_k = r_k · e^(i·θ_k) = r_k · (cos θ_k  +  i · sin θ_k)

Where:
    r_k  ∈ (0, 1)  — contraction rate (decay toward stability)
    θ_k  ∈ ℝ       — oscillation frequency (learned)
    |A_k| = r_k < 1 — guaranteed stability (all eigenvalues inside unit circle)

The state transition becomes a rotation-then-contraction in the complex plane:

    h'_r = r · (cos θ · h_r  −  sin θ · h_i)  +  B_r · x
    h'_i = r · (sin θ · h_r  +  cos θ · h_i)  +  B_i · x
    y    = C_r · h_r  +  C_i · h_i  +  D · x

This is Euler's formula as the core state update — every step is a rotation
by θ (how much the memory oscillates) contracted by r (how much it forgets).

Why this matters for knowledge graphs:
    - Topics in Obsidian recur at different frequencies (daily notes, projects, themes)
    - Real-valued SSMs can only exponentially decay — they can't naturally represent
      cyclical, oscillatory memory about recurring concepts
    - Complex Euler poles near the unit circle hold long-range oscillatory memory
    - Different (r, θ) pairs specialize to different note-recurrence timescales

Implementation:
    States are tracked as paired reals (h_r, h_i) to avoid complex dtype overhead.
    B and C are also split into real/imaginary components.
    Output is always real: y = Re(C · h) + D · x — so the model output stays
    compatible with the rest of the real-valued GNN pipeline.

Parameter count: identical to SelectiveSSM — no budget change.
    Old: A_log   (d_inner × d_state) real
    New: theta   (d_inner × d_state//2) + r_log (d_inner × d_state//2)
         = d_inner × d_state  ← same

Reference:
    Euler's formula: e^(iθ) = cos θ + i·sin θ   (Euler, 1748)
    S4/DSS complex SSMs: Gu et al. (2022), Gupta et al. (2022)
    Applied to GNN walk dynamics: this work
"""
import math
from typing import Optional

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


class EulerSSM(nn.Module):
    """
    Drop-in replacement for SelectiveSSM using complex Euler parameterization.

    State space dimension d_state must be even (pairs of real/imaginary).

    Args:
        d_model:  input and output feature dimension
        d_state:  SSM state dimension (must be even — split into N/2 complex pairs)
        d_conv:   depthwise conv kernel size (same as SelectiveSSM)
    """

    def __init__(self, d_model: int, d_state: int = 64, d_conv: int = 4) -> None:
        super().__init__()
        assert d_state % 2 == 0, "d_state must be even for complex Euler pairs"
        self.d_model = d_model
        self.d_state = d_state
        self.d_pairs = d_state // 2    # number of complex conjugate pairs
        self.d_inner = d_model
        self.d_conv = d_conv

        # ── Input projection (same as SelectiveSSM) ────────────────────────
        self.in_proj = nn.Linear(d_model, 2 * self.d_inner, bias=False)

        # ── Depthwise conv along walk sequence ────────────────────────────
        self.conv1d = nn.Conv1d(
            in_channels=self.d_inner,
            out_channels=self.d_inner,
            kernel_size=d_conv,
            padding=d_conv - 1,
            groups=self.d_inner,
            bias=True,
        )

        # ── Euler eigenvalue parameters ────────────────────────────────────
        # theta: learned oscillation frequencies (one per complex pair per channel)
        # Shape: (d_inner, d_pairs)
        # Initialized near 0 (slow oscillation), will learn meaningful frequencies
        self.theta = nn.Parameter(
            torch.linspace(0, math.pi, self.d_pairs)
            .unsqueeze(0)
            .expand(self.d_inner, -1)
            .clone()
        )

        # r_log: log of contraction rate, constrained to (0,1) via sigmoid
        # Shape: (d_inner, d_pairs)
        # Initialized so r ≈ 0.9 (slow decay = long memory)
        self.r_log = nn.Parameter(
            torch.full((self.d_inner, self.d_pairs), math.log(0.9 / (1 - 0.9)))
        )

        # ── Input-selective B projection (complex: real + imaginary) ───────
        # x_proj: d_inner → (B_r, B_i, C_r, C_i, dt)
        # = d_pairs + d_pairs + d_pairs + d_pairs + 1 = 4·d_pairs + 1
        self.x_proj = nn.Linear(self.d_inner, 4 * self.d_pairs + 1, bias=False)
        self.dt_proj = nn.Linear(1, self.d_inner, bias=True)

        # ── Skip connection ────────────────────────────────────────────────
        self.D = nn.Parameter(torch.ones(self.d_inner))

        # ── Output projection ──────────────────────────────────────────────
        self.out_proj = nn.Linear(self.d_inner, d_model, bias=False)

    # ──────────────────────────────────────────────────────────────────────────
    # Euler rotation kernel
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def euler_rotate(
        h_r: torch.Tensor,  # (..., d_pairs)
        h_i: torch.Tensor,  # (..., d_pairs)
        theta: torch.Tensor,  # (..., d_pairs)
        r: torch.Tensor,      # (..., d_pairs)
    ):
        """
        Apply Euler rotation: h' = r · e^(iθ) · h

        In real coordinates:
            h'_r = r · (cos θ · h_r − sin θ · h_i)
            h'_i = r · (sin θ · h_r + cos θ · h_i)

        This is the heart of the Euler SSM — each step is a
        rotation (Euler's formula) followed by a contraction (stability).
        """
        cos_t = torch.cos(theta)
        sin_t = torch.sin(theta)
        new_r = r * (cos_t * h_r - sin_t * h_i)
        new_i = r * (sin_t * h_r + cos_t * h_i)
        return new_r, new_i

    # ──────────────────────────────────────────────────────────────────────────
    # Forward
    # ──────────────────────────────────────────────────────────────────────────

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch, seq_len, d_model)

        Returns:
            y: (batch, seq_len, d_model)
        """
        B, L, _ = x.shape

        xz = self.in_proj(x)                         # (B, L, 2·d_inner)
        x_in, z = xz.chunk(2, dim=-1)               # each (B, L, d_inner)

        # depthwise conv (local context along walk axis)
        x_conv = rearrange(x_in, "b l d -> b d l")
        x_conv = self.conv1d(x_conv)[..., :L]
        x_conv = rearrange(x_conv, "b d l -> b l d")
        x_conv = F.silu(x_conv)                      # (B, L, d_inner)

        # selective projections
        proj = self.x_proj(x_conv)                   # (B, L, 4·d_pairs+1)
        B_r  = proj[..., :self.d_pairs]              # (B, L, d_pairs)
        B_i  = proj[..., self.d_pairs:2*self.d_pairs]
        C_r  = proj[..., 2*self.d_pairs:3*self.d_pairs]
        C_i  = proj[..., 3*self.d_pairs:4*self.d_pairs]
        dt_raw = proj[..., -1:]                      # (B, L, 1)

        # time step: input-dependent, positive
        dt = F.softplus(self.dt_proj(dt_raw))        # (B, L, d_inner)

        # Euler eigenvalue: r ∈ (0,1), theta ∈ ℝ
        r = torch.sigmoid(self.r_log)                # (d_inner, d_pairs) ∈ (0,1)
        theta = self.theta                           # (d_inner, d_pairs)

        # dt modulates the effective rotation angle and contraction
        # discretization: dA = A^dt ≈ r^dt · e^(i·θ·dt)
        # → r_eff = r^dt,  θ_eff = θ·dt  (input-selective Euler step)
        dt_mean = dt.mean(dim=-1, keepdim=True)      # (B, L, 1)
        r_eff   = r.unsqueeze(0).unsqueeze(0) ** dt_mean.unsqueeze(-1)  # (B,L,d_inner,d_pairs)
        theta_eff = theta.unsqueeze(0).unsqueeze(0) * dt_mean.unsqueeze(-1)

        # ── Sequential Euler scan over walk positions ──────────────────────
        # h_r, h_i: (B, d_inner, d_pairs)
        h_r = torch.zeros(B, self.d_inner, self.d_pairs, device=x.device, dtype=x.dtype)
        h_i = torch.zeros(B, self.d_inner, self.d_pairs, device=x.device, dtype=x.dtype)

        ys = []
        for t in range(L):
            # Euler rotation-contraction for this step
            h_r, h_i = self.euler_rotate(
                h_r, h_i,
                theta_eff[:, t],   # (B, d_inner, d_pairs)
                r_eff[:, t],
            )

            # selective input injection: B is per-channel, B_r/B_i are per-pair
            # broadcast x_conv along d_pairs
            x_t = x_conv[:, t]                      # (B, d_inner)
            B_r_t = B_r[:, t]                       # (B, d_pairs)
            B_i_t = B_i[:, t]

            # inject: expand x_t across pairs then add gated input
            h_r = h_r + x_t.unsqueeze(-1) * B_r_t.unsqueeze(1)  # (B, d_inner, d_pairs)
            h_i = h_i + x_t.unsqueeze(-1) * B_i_t.unsqueeze(1)

            # output: y = Re(C · h) = C_r · h_r + C_i · h_i
            # C is per-pair, sum over d_pairs → (B, d_inner)
            C_r_t = C_r[:, t]   # (B, d_pairs)
            C_i_t = C_i[:, t]
            y_t = (h_r * C_r_t.unsqueeze(1)).sum(-1) \
                + (h_i * C_i_t.unsqueeze(1)).sum(-1)   # (B, d_inner)
            ys.append(y_t)

        y = torch.stack(ys, dim=1)                   # (B, L, d_inner)

        # gated output + skip (same as SelectiveSSM)
        y = y * F.silu(z)
        y = y + x_conv * self.D.unsqueeze(0).unsqueeze(0)
        return self.out_proj(y)                      # (B, L, d_model)

    # ──────────────────────────────────────────────────────────────────────────
    # Inspection helpers
    # ──────────────────────────────────────────────────────────────────────────

    def get_eigenvalues(self) -> torch.Tensor:
        """
        Return complex eigenvalues A_k = r_k · e^(i·θ_k).
        Shape: (d_inner, d_pairs) complex.
        Visualise to see what oscillation frequencies the model has learned.
        """
        r = torch.sigmoid(self.r_log)
        cos_t = torch.cos(self.theta)
        sin_t = torch.sin(self.theta)
        return torch.complex(r * cos_t, r * sin_t)

    def eigenvalue_summary(self) -> dict:
        """Human-readable summary of learned Euler eigenvalue statistics."""
        r = torch.sigmoid(self.r_log).detach()
        theta = self.theta.detach()
        return {
            "r_mean":     r.mean().item(),
            "r_min":      r.min().item(),
            "r_max":      r.max().item(),
            "theta_mean": theta.mean().item(),
            "theta_std":  theta.std().item(),
            "freq_Hz_mean": (theta / (2 * math.pi)).abs().mean().item(),
        }
