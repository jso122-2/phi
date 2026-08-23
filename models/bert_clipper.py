"""
BERTClipper — lightweight numpy attention encoder (perpetual pretraining).

Architecture (ARCHITECTURE LOCKED — pow.md):

    Sits above SSMCore in the Octopus Tracer pipeline.

    Emits:
        H         ∈ ℝ^(N×d)   node embeddings  → SSMCore.tick() input
        tau       ∈ ℝ⁺        temperature       → SCUP cosine scaling
        lora_proj ∈ ℝ^(d×r)   projection slice  → LoRA sucker inheritance at spawn

    Layer structure (n_layers=2, n_heads=4, d_head=d//n_heads):
        embed    : X_raw (N×d_in) → X_emb (N×d)  W_emb (d_in×d) + b_emb (d)
        per layer:
            self-attention : W_Q, W_K, W_V, W_O (d×d each) + residual + LayerNorm
            FFN            : W_ff1 (d×d_ff) + W_ff2 (d_ff×d) + residual + LayerNorm
        tau head           : softplus(mean(H) @ w_tau)

    lora_proj = W_O[:, :lora_rank] from the last attention layer → (d, lora_rank)
    Passed to LoRASucker(A_init=lora_proj) at spawn for BERT-weight inheritance.

    Perpetual pretraining (denoising autoencoder):
        update(X, lr, noise_std)
            — adds Gaussian noise, reconstructs X via W_out,
              computes MSE, clips global gradient norm, updates W_emb + W_out.

Parameter budget (d=256, n_layers=2, n_heads=4, d_ff=1024):
    embed     : 256×256 + 256  =  65,792
    2 layers  : 2 × (4×256×256 + 2×256 + 256×1024 + 1024 + 1024×256 + 256 + 2×256)
              ≈ 2 × 786,432     = 1,572,864
    W_out     : 256×256        =  65,536
    w_tau     : 256            =      256
    Total                      ≈ 1.7M   (pow.md: "lives above — not counted")
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Layer parameter container
# ---------------------------------------------------------------------------

@dataclass
class _AttnLayer:
    W_Q:     np.ndarray   # (d, d)
    W_K:     np.ndarray   # (d, d)
    W_V:     np.ndarray   # (d, d)
    W_O:     np.ndarray   # (d, d)
    gamma_1: np.ndarray   # (d,)  LN scale after attention
    beta_1:  np.ndarray   # (d,)  LN bias after attention
    W_ff1:   np.ndarray   # (d, d_ff)
    b_ff1:   np.ndarray   # (d_ff,)
    W_ff2:   np.ndarray   # (d_ff, d)
    b_ff2:   np.ndarray   # (d,)
    gamma_2: np.ndarray   # (d,)  LN scale after FFN
    beta_2:  np.ndarray   # (d,)  LN bias after FFN


# ---------------------------------------------------------------------------
# BERTClipper
# ---------------------------------------------------------------------------

class BERTClipper:
    """
    Multi-head self-attention encoder with perpetual denoising pretraining.

    Parameters
    ----------
    d_in      : input feature dimension (default 256)
    d         : internal / output embedding dimension (default 256)
    n_layers  : attention blocks (default 2)
    n_heads   : attention heads; must divide d evenly (default 4)
    d_ff      : FFN hidden width; default 4×d
    lora_rank : rank r for lora_proj output slice (default 8)
    clip_norm : gradient clip norm for update() (default 1.0)
    rng       : numpy Generator
    """

    def __init__(
        self,
        d_in: int = 256,
        d: int = 256,
        n_layers: int = 2,
        n_heads: int = 4,
        d_ff: Optional[int] = None,
        lora_rank: int = 8,
        clip_norm: float = 1.0,
        rng: Optional[np.random.Generator] = None,
    ) -> None:
        if d % n_heads != 0:
            raise ValueError(f"d={d} must be divisible by n_heads={n_heads}")
        self.d_in     = d_in
        self.d        = d
        self.n_layers = n_layers
        self.n_heads  = n_heads
        self.d_head   = d // n_heads
        self.d_ff     = d_ff if d_ff is not None else 4 * d
        self.lora_rank = lora_rank
        self.clip_norm = clip_norm
        rng = rng or np.random.default_rng(0)

        sc = 0.02

        # Input embedding projection
        if d_in == d:
            self.W_emb: np.ndarray = np.eye(d, dtype=np.float64)
        else:
            self.W_emb = rng.standard_normal((d_in, d)).astype(np.float64) * sc
        self.b_emb: np.ndarray = np.zeros(d, dtype=np.float64)

        # Attention layers
        self.layers: list[_AttnLayer] = [
            _AttnLayer(
                W_Q=rng.standard_normal((d, d)).astype(np.float64) * sc,
                W_K=rng.standard_normal((d, d)).astype(np.float64) * sc,
                W_V=rng.standard_normal((d, d)).astype(np.float64) * sc,
                W_O=rng.standard_normal((d, d)).astype(np.float64) * sc,
                gamma_1=np.ones(d, dtype=np.float64),
                beta_1=np.zeros(d, dtype=np.float64),
                W_ff1=rng.standard_normal((d, self.d_ff)).astype(np.float64) * sc,
                b_ff1=np.zeros(self.d_ff, dtype=np.float64),
                W_ff2=rng.standard_normal((self.d_ff, d)).astype(np.float64) * sc,
                b_ff2=np.zeros(d, dtype=np.float64),
                gamma_2=np.ones(d, dtype=np.float64),
                beta_2=np.zeros(d, dtype=np.float64),
            )
            for _ in range(n_layers)
        ]

        # Output readout for denoising reconstruction (d → d_in)
        self.W_out: np.ndarray = rng.standard_normal((d, d_in)).astype(np.float64) * sc

        # Temperature scalar head
        self.w_tau: np.ndarray = rng.standard_normal(d).astype(np.float64) * sc

    # ------------------------------------------------------------------
    # Private ops
    # ------------------------------------------------------------------

    @staticmethod
    def _layer_norm(
        x: np.ndarray,
        gamma: np.ndarray,
        beta: np.ndarray,
        eps: float = 1e-6,
    ) -> np.ndarray:
        mu  = x.mean(axis=-1, keepdims=True)
        var = x.var(axis=-1, keepdims=True)
        return gamma * (x - mu) / np.sqrt(var + eps) + beta

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        x = x - x.max(axis=-1, keepdims=True)
        e = np.exp(x)
        return e / e.sum(axis=-1, keepdims=True)

    @staticmethod
    def _gelu(x: np.ndarray) -> np.ndarray:
        return 0.5 * x * (1.0 + np.tanh(math.sqrt(2.0 / math.pi) * (x + 0.044715 * x ** 3)))

    @staticmethod
    def _softplus(x: float) -> float:
        return math.log1p(math.exp(float(np.clip(x, -80, 80))))

    def _mhsa(self, X: np.ndarray, layer: _AttnLayer) -> np.ndarray:
        """Multi-head self-attention forward."""
        N = X.shape[0]
        Q = (X @ layer.W_Q).reshape(N, self.n_heads, self.d_head).transpose(1, 0, 2)
        K = (X @ layer.W_K).reshape(N, self.n_heads, self.d_head).transpose(1, 0, 2)
        V = (X @ layer.W_V).reshape(N, self.n_heads, self.d_head).transpose(1, 0, 2)
        scores = (Q @ K.transpose(0, 2, 1)) / math.sqrt(self.d_head)
        attn   = self._softmax(scores)                         # (n_heads, N, N)
        out    = (attn @ V).transpose(1, 0, 2).reshape(N, self.d)  # (N, d)
        return out @ layer.W_O                                 # (N, d)

    def _block(self, X: np.ndarray, layer: _AttnLayer) -> np.ndarray:
        """One transformer block: MHSA + FFN with residuals and layer-norm."""
        X = self._layer_norm(X + self._mhsa(X, layer), layer.gamma_1, layer.beta_1)
        ff = self._gelu(X @ layer.W_ff1 + layer.b_ff1) @ layer.W_ff2 + layer.b_ff2
        return self._layer_norm(X + ff, layer.gamma_2, layer.beta_2)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def encode(self, X: np.ndarray) -> tuple[np.ndarray, float, np.ndarray]:
        """
        Forward pass.

        Parameters
        ----------
        X : (N, d_in)  raw node features

        Returns
        -------
        H         : (N, d)      node embeddings — SSMCore input
        tau       : float       temperature ∈ ℝ⁺
        lora_proj : (d, r)      projection for LoRA sucker inheritance
        """
        X = np.asarray(X, dtype=np.float64)
        H = X @ self.W_emb + self.b_emb   # (N, d)
        for layer in self.layers:
            H = self._block(H, layer)
        # Temperature: softplus(mean_node(H) · w_tau)
        tau = self._softplus(float(H.mean(axis=0) @ self.w_tau))
        tau = max(tau, 1e-6)
        # LoRA projection: W_O from last layer, first lora_rank columns
        lora_proj = self.layers[-1].W_O[:, :self.lora_rank].copy()   # (d, lora_rank)
        return H, tau, lora_proj

    def update(
        self,
        X: np.ndarray,
        target: Optional[np.ndarray] = None,
        lr: float = 1e-4,
        noise_std: float = 0.1,
    ) -> float:
        """
        One denoising pretraining step (perpetual pretraining).

        Adds Gaussian noise to X, encodes the noisy version, reconstructs
        via W_out, computes MSE against target (default: clean X), clips
        the global gradient norm to clip_norm, then updates W_emb and W_out.

        Attention layer weights are not updated — they provide the structural
        inductive bias and their projections are inherited by LoRA suckers.

        Parameters
        ----------
        X         : (N, d_in) clean node features
        target    : (N, d_in) reconstruction target; defaults to X
        lr        : learning rate
        noise_std : Gaussian noise std for denoising objective

        Returns
        -------
        loss : float  MSE before the update step
        """
        X = np.asarray(X, dtype=np.float64)
        if target is None:
            target = X
        target = np.asarray(target, dtype=np.float64)
        N = X.shape[0]

        # Denoising input
        noise   = np.random.default_rng().standard_normal(X.shape).astype(np.float64) * noise_std
        X_noisy = X + noise

        # Forward: embed → blocks → readout
        X_emb = X_noisy @ self.W_emb + self.b_emb   # (N, d)
        H = X_emb
        for layer in self.layers:
            H = self._block(H, layer)
        pred = H @ self.W_out                         # (N, d_in)
        err  = pred - target                          # (N, d_in)
        loss = float(np.mean(err ** 2))

        # Gradients
        # W_out: ∂L/∂W_out = H.T @ err / N
        grad_W_out = H.T @ err / N                   # (d, d_in)
        # W_emb: first-order approx ignoring attention non-linearity
        # ∂H_emb/∂W_emb ≈ X_noisy.T,  ∂L/∂H ≈ err @ W_out.T
        grad_H_emb = err @ self.W_out.T              # (N, d)
        grad_W_emb = X_noisy.T @ grad_H_emb / N     # (d_in, d)

        # Global gradient norm clipping
        sq_sum = float(np.sum(grad_W_out ** 2) + np.sum(grad_W_emb ** 2))
        grad_norm = math.sqrt(sq_sum)
        if grad_norm > self.clip_norm and grad_norm > 1e-12:
            scale      = self.clip_norm / grad_norm
            grad_W_out *= scale
            grad_W_emb *= scale

        self.W_out -= lr * grad_W_out
        self.W_emb -= lr * grad_W_emb

        return loss

    def save(self, path: str | Path) -> None:
        """Persist embedding, attention, and readout weights to an npz."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, np.ndarray] = {
            "d_in": np.array(self.d_in),
            "d": np.array(self.d),
            "n_layers": np.array(self.n_layers),
            "n_heads": np.array(self.n_heads),
            "d_ff": np.array(self.d_ff),
            "lora_rank": np.array(self.lora_rank),
            "clip_norm": np.array(self.clip_norm),
            "W_emb": self.W_emb,
            "b_emb": self.b_emb,
            "W_out": self.W_out,
            "w_tau": self.w_tau,
        }
        for i, layer in enumerate(self.layers):
            for field_name in (
                "W_Q", "W_K", "W_V", "W_O",
                "gamma_1", "beta_1", "W_ff1", "b_ff1",
                "W_ff2", "b_ff2", "gamma_2", "beta_2",
            ):
                payload[f"L{i}_{field_name}"] = getattr(layer, field_name)
        np.savez(path, **payload)

    @classmethod
    def load(cls, path: str | Path) -> "BERTClipper":
        """Load weights written by save()."""
        data = np.load(path)
        inst = cls.__new__(cls)
        inst.d_in = int(data["d_in"])
        inst.d = int(data["d"])
        inst.n_layers = int(data["n_layers"])
        inst.n_heads = int(data["n_heads"])
        inst.d_head = inst.d // inst.n_heads
        inst.d_ff = int(data["d_ff"])
        inst.lora_rank = int(data["lora_rank"])
        inst.clip_norm = float(data["clip_norm"])
        inst.W_emb = np.asarray(data["W_emb"], dtype=np.float64)
        inst.b_emb = np.asarray(data["b_emb"], dtype=np.float64)
        inst.W_out = np.asarray(data["W_out"], dtype=np.float64)
        inst.w_tau = np.asarray(data["w_tau"], dtype=np.float64)
        inst.layers = []
        for i in range(inst.n_layers):
            inst.layers.append(_AttnLayer(
                W_Q=np.asarray(data[f"L{i}_W_Q"], dtype=np.float64),
                W_K=np.asarray(data[f"L{i}_W_K"], dtype=np.float64),
                W_V=np.asarray(data[f"L{i}_W_V"], dtype=np.float64),
                W_O=np.asarray(data[f"L{i}_W_O"], dtype=np.float64),
                gamma_1=np.asarray(data[f"L{i}_gamma_1"], dtype=np.float64),
                beta_1=np.asarray(data[f"L{i}_beta_1"], dtype=np.float64),
                W_ff1=np.asarray(data[f"L{i}_W_ff1"], dtype=np.float64),
                b_ff1=np.asarray(data[f"L{i}_b_ff1"], dtype=np.float64),
                W_ff2=np.asarray(data[f"L{i}_W_ff2"], dtype=np.float64),
                b_ff2=np.asarray(data[f"L{i}_b_ff2"], dtype=np.float64),
                gamma_2=np.asarray(data[f"L{i}_gamma_2"], dtype=np.float64),
                beta_2=np.asarray(data[f"L{i}_beta_2"], dtype=np.float64),
            ))
        return inst

    @classmethod
    def load_default(cls, d: int = 256, path: str | Path | None = None) -> "BERTClipper":
        ckpt = Path(path) if path is not None else Path.home() / ".phi" / "bert_clipper.npz"
        if ckpt.exists():
            return cls.load(ckpt)
        return cls(d_in=d, d=d)

    @property
    def n_params(self) -> int:
        """Total learnable scalar parameter count."""
        p = self.d_in * self.d + self.d
        for _ in self.layers:
            p += 4 * self.d * self.d
            p += 4 * self.d                              # gamma_1, beta_1, gamma_2, beta_2
            p += self.d * self.d_ff + self.d_ff
            p += self.d_ff * self.d + self.d
        p += self.d * self.d_in                          # W_out
        p += self.d                                      # w_tau
        return p

    def __repr__(self) -> str:
        return (
            f"<BERTClipper d_in={self.d_in} d={self.d} "
            f"n_layers={self.n_layers} n_heads={self.n_heads} "
            f"lora_rank={self.lora_rank} n_params≈{self.n_params:,}>"
        )
