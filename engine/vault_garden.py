# -*- coding: utf-8 -*-
"""
engine.vault_garden — Obsidian vault graph → TracerDaemon one cycle.

This is the runtime entry point for gardening-mode OctopusTracer operation.
Instead of music-library tracks (PhiOrchestrator), the input is the vault
knowledge graph — every VaultNode is a graph vertex.

Pipeline
--------
  1. load_vault()            →  list[VaultNode]  (N nodes)
  2. embed_nodes(nodes)      →  X (N, d_embed)   fastembed text embeddings
  3. build_adjacency(nodes)  →  A (N, N)         wikilink edges (directed → symmetric)
  4. project(X, d_model)     →  X_proj (N, d)    random-projection to d_model dims
  5. TracerDaemon.run_once(A, X_proj)
                             →  TracerSummary
                             →  SambaWriter vault writes (if coherence ≥ gate)

Usage
-----
    from engine.vault_garden import VaultGarden

    garden = VaultGarden(vault_root=Path("."))
    summary = garden.run_cycle()
    print(summary.as_dict())

The CAIRRN coherence gate inside TracerDaemon controls write authority.
On the first cycle (tick=0) coherence=1.0 → writes are live.
Arms will be suppressed on subsequent cycles until tick resets.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

from graph.node import VaultNode, load_vault
from engine.tracer_daemon import TracerDaemon, TracerSummary

logger = logging.getLogger(__name__)

# Default fastembed model dimension (BAAI/bge-small-en-v1.5 → 384)
_DEFAULT_D_EMBED = 384
# TracerDaemon default model dimension
_DEFAULT_D_MODEL = 256
# Random projection seed — fixed for reproducibility across cycles
_PROJ_SEED = 0xC0FFEE


# ---------------------------------------------------------------------------
# Stateless helpers (independently testable)
# ---------------------------------------------------------------------------


def build_adjacency(nodes: list[VaultNode]) -> np.ndarray:
    """
    Build a symmetric boolean adjacency matrix from vault wikilinks.

    Each wikilink in node ``u`` to node ``v`` sets A[u, v] = A[v, u] = 1.
    Path-prefixed links (e.g. ``keep/foo-bar``) are resolved to their bare stem.
    Self-loops are zeroed.

    Args:
        nodes: Ordered list of VaultNode objects.

    Returns:
        A (N, N) float64 adjacency matrix with 0/1 entries.
    """
    stems = {n.stem: i for i, n in enumerate(nodes)}
    N = len(nodes)
    A = np.zeros((N, N), dtype=np.float64)

    for i, node in enumerate(nodes):
        for link in node.wikilinks:
            bare = link.rsplit("/", 1)[-1]
            j = stems.get(bare)
            if j is not None and j != i:
                A[i, j] = 1.0
                A[j, i] = 1.0   # symmetric — undirected gardening graph

    return A


def embed_nodes(nodes: list[VaultNode], batch_size: int = 64) -> np.ndarray:
    """
    Embed vault node text using fastembed TextEmbedding (BAAI/bge-small-en-v1.5).

    Each node's embedding is computed from: ``title + " " + first 512 chars of text``.
    Returns a (N, d_embed) float32 array.  Falls back to random normal embeddings
    if fastembed is unavailable (tests / environments without the model).

    Args:
        nodes:      Ordered list of VaultNode objects.
        batch_size: Streaming batch size passed to fastembed.

    Returns:
        X (N, d_embed) float32 array.
    """
    texts = [_node_text(n) for n in nodes]

    try:
        from fastembed import TextEmbedding
        model = TextEmbedding()
        vecs = list(model.embed(texts, batch_size=batch_size))
        X = np.array(vecs, dtype=np.float32)
        logger.info("embed_nodes: N=%d  d=%d  (fastembed)", len(nodes), X.shape[1])
        return X
    except Exception as exc:
        logger.warning(
            "embed_nodes: fastembed unavailable (%s) — using random embeddings", exc
        )
        rng = np.random.default_rng(42)
        return rng.standard_normal((len(nodes), _DEFAULT_D_EMBED)).astype(np.float32)


def project_embeddings(X: np.ndarray, d_out: int, seed: int = _PROJ_SEED) -> np.ndarray:
    """
    Random orthogonal projection from d_in → d_out dimensions.

    Uses a fixed seed so the projection matrix is stable across cycles.
    When d_in == d_out, returns X unchanged.

    Args:
        X:    (N, d_in) float array.
        d_out: Target dimension.
        seed:  RNG seed for the projection matrix.

    Returns:
        (N, d_out) float64 array.
    """
    d_in = X.shape[1]
    if d_in == d_out:
        return X.astype(np.float64)

    rng = np.random.default_rng(seed)
    P = rng.standard_normal((d_in, d_out)).astype(np.float64)
    # Column-normalise so projected norms stay near 1
    P /= np.linalg.norm(P, axis=0, keepdims=True).clip(min=1e-9)
    return (X.astype(np.float64) @ P)


def _node_text(node: VaultNode, max_chars: int = 512) -> str:
    """Combine title + truncated body for embedding."""
    body = node.text[:max_chars].replace("\n", " ").strip()
    return f"{node.title} {body}"


# ---------------------------------------------------------------------------
# VaultGarden — stateful orchestrator
# ---------------------------------------------------------------------------


class VaultGarden:
    """
    Drives one OctopusTracer gardening cycle over the Obsidian vault graph.

    Each call to ``run_cycle()`` loads the live vault, embeds nodes, builds
    the adjacency matrix, and feeds everything into TracerDaemon.run_once().
    If the CAIRRN coherence gate allows writes, arm scores are committed to
    the vault via SambaWriter (``sessions/samba/`` directory).

    Args:
        vault_root:   Path to the vault root.  If None, uses graph.node.VAULT_ROOT.
        d_model:      TracerDaemon model dimension (default 256).
        max_tracers:  Hard cap on concurrent tracers in the pool.
        embed_batch:  fastembed streaming batch size.
    """

    def __init__(
        self,
        vault_root: Optional[Path] = None,
        d_model: int = _DEFAULT_D_MODEL,
        max_tracers: int = 8,
        embed_batch: int = 64,
    ) -> None:
        if vault_root is None:
            from graph.node import VAULT_ROOT
            vault_root = VAULT_ROOT

        self._vault_root = Path(vault_root)
        self._embed_batch = embed_batch

        self._daemon = TracerDaemon(
            max_tracers=max_tracers,
            d=d_model,
            vault_root=self._vault_root,
        )

        logger.info(
            "VaultGarden initialised  vault=%s  d=%d  max_tracers=%d",
            self._vault_root.name, d_model, max_tracers,
        )

    # ── public API ────────────────────────────────────────────────────────────

    def run_cycle(
        self,
        vault: Optional[list[VaultNode]] = None,
    ) -> TracerSummary:
        """
        Execute one gardening cycle.

        Args:
            vault:  Pre-loaded list of VaultNode objects.  If None, calls
                    load_vault() to read the live vault from disk.

        Returns:
            TracerSummary with aggregated arm scores, tick, coherence metadata.
            If coherence ≥ COHERENCE_THRESHOLD, SambaWriter has written arm
            output nodes to ``<vault_root>/sessions/samba/``.
        """
        nodes = vault if vault is not None else load_vault()
        if not nodes:
            logger.warning("VaultGarden.run_cycle: vault is empty — cycle skipped.")
            # Return a zero summary so callers don't need to handle None
            from engine.tracer_daemon import _aggregate_tracers
            return _aggregate_tracers([])

        logger.info("VaultGarden.run_cycle: N=%d vault nodes", len(nodes))

        A     = build_adjacency(nodes)
        X_raw = embed_nodes(nodes, batch_size=self._embed_batch)
        X     = project_embeddings(X_raw, d_out=self._daemon.d)

        summary = self._daemon.run_once(A=A, X=X)

        logger.info(
            "VaultGarden.run_cycle done  tick=%d  tracers=%d  "
            "coherence=%.3f  prune=%.3f  sprout=%.3f",
            self._daemon.tick,
            summary.n_tracers,
            summary.mean_coherence,
            summary.arm_prune,
            summary.arm_sprout,
        )
        return summary

    # ── accessors ─────────────────────────────────────────────────────────────

    @property
    def daemon(self) -> TracerDaemon:
        return self._daemon

    @property
    def tick(self) -> int:
        return self._daemon.tick

    @property
    def samba_dir(self) -> Path:
        from engine.vault_writer import SAMBA_SUBDIR
        return self._vault_root / SAMBA_SUBDIR

    def __repr__(self) -> str:
        return (
            f"<VaultGarden vault={self._vault_root.name!r} "
            f"tick={self.tick}>"
        )
