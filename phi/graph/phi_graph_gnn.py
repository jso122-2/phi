# -*- coding: utf-8 -*-
"""phi.graph.phi_graph — PhiGraph: track graph for OctopusTracer ingestion.

Analogous to topology.TopologicalGraph for the Obsidian vault, but built over
Phi's track library using CLAP audio embeddings as node features.

Nodes are tracks.  Edges are implicit — the OctopusTracer uses soft_edge_mode
by default and computes soft edges dynamically from H via sigmoid cosine
similarity, so no explicit adjacency matrix is required.  Call adjacency() only
for full regression mode or external analysis.

Usage
─────
    proj  = CLAPProjection()                          # or load from checkpoint
    graph = PhiGraph(library, proj)
    snap  = graph.build()
    # snap.H      — (N, 256) tensor ready for OctopusTracer
    # snap.paths  — parallel track paths (index == node row in H)

    tracer_out = octopus_tracer(snap.H)
    # sprout score > threshold at index i → library gap near track snap.paths[i]

Reference: OctopusTracer soft-edge mode — models/octopus_tracer.py
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import numpy as np

from phi.models.clap_proj import CLAPProjection

if TYPE_CHECKING:
    from phi.core.library import Library

logger = logging.getLogger(__name__)

# Cosine similarity threshold for explicit adjacency construction.
# Mirrors config.yaml edges.semantic_threshold (0.65) used in the Samba vault graph.
DEFAULT_SIM_THRESHOLD: float = 0.65


@dataclass
class PhiGraphSnapshot:
    """
    Immutable output of one PhiGraph.build() call.

    Attributes
    ──────────
    H:             (N, d_model) projected track embeddings — direct OctopusTracer input
    paths:         ordered track paths, len == N
    n_tracks:      total tracks in library at build time
    n_embedded:    tracks with CLAP embeddings (== N)
    n_missing:     tracks without CLAP embeddings (can't be graphed until CLAPModel runs)
    sim_threshold: cosine threshold used by adjacency() (informational)
    """

    H:             np.ndarray
    paths:         list[str]
    n_tracks:      int
    n_embedded:    int
    n_missing:     int
    sim_threshold: float = DEFAULT_SIM_THRESHOLD
    _adj:          Optional[np.ndarray] = field(default=None, repr=False)

    # D4 scores — populated by derivative_bridge.score_and_attach().
    # Shape: (N,) float32 ndarray, aligned to paths.  NaN for unscored tracks.
    # None until score_and_attach() has been called on this snapshot.
    d4_scores:     Optional[np.ndarray] = field(default=None, repr=False)

    # ── node lookup ──────────────────────────────────────────────────────────

    def index_of(self, path: str) -> Optional[int]:
        """Row index of *path* in H, or None if not embedded."""
        try:
            return self.paths.index(path)
        except ValueError:
            return None

    def path_of(self, idx: int) -> Optional[str]:
        """Track path for row *idx*, or None if out of range."""
        return self.paths[idx] if 0 <= idx < len(self.paths) else None

    def top_k_similar(self, idx: int, k: int = 5) -> list[tuple[int, float]]:
        """
        Return the top-k most similar tracks to the track at *idx*.

        Computed with cosine similarity over H without building the full matrix.

        Args:
            idx: row index in H
            k:   number of neighbours to return

        Returns:
            list of (other_idx, cosine_similarity) sorted descending
        """
        assert 0 <= idx < len(self.paths), f"idx {idx} out of range [0, {len(self.paths)})"
        h_q  = self.H[idx]                          # (D,)
        norms = np.linalg.norm(self.H, axis=1) * np.linalg.norm(h_q)
        norms = np.where(norms == 0, 1.0, norms)
        sims  = self.H @ h_q / norms               # (N,) cosine similarity
        sims[idx] = -1.0                             # suppress self
        k_actual = min(k, max(len(self.paths) - 1, 1))
        top_idx  = np.argpartition(sims, -k_actual)[-k_actual:]
        top_idx  = top_idx[np.argsort(sims[top_idx])[::-1]]
        return [(int(i), float(sims[i])) for i in top_idx]

    # ── stats ─────────────────────────────────────────────────────────────────

    def coverage_pct(self) -> float:
        return round(self.n_embedded / max(self.n_tracks, 1) * 100, 1)

    def summary(self) -> dict:
        d4_coverage = 0
        if self.d4_scores is not None:
            d4_coverage = int((~np.isnan(self.d4_scores)).sum())
        return {
            "n_tracks":      self.n_tracks,
            "n_embedded":    self.n_embedded,
            "n_missing":     self.n_missing,
            "coverage_pct":  self.coverage_pct(),
            "h_shape":       list(self.H.shape),  # works for both np.ndarray and torch.Tensor
            "d4_scored":     d4_coverage,
        }


class PhiGraph:
    """
    Builds a projected embedding graph over a Phi Library for OctopusTracer ingestion.

    The graph operates in soft-edge mode by default: no adjacency matrix is
    pre-built.  OctopusTracer computes soft edges dynamically from H via
    sigmoid cosine similarity (see _soft_edge_R in OctopusTracer).

    Call adjacency() explicitly only when using OctopusTracer in full regression
    mode (soft_edge_mode=False) or for external topological analysis.

    Safe to call build() multiple times — each call reflects the current state
    of the library, matching the TopologicalGraph.build() lifecycle contract used
    by CoherenceDaemon.

    Args:
        library:       Phi Library instance (source of annotations)
        projection:    CLAPProjection — projects 512-d CLAP vecs → 256-d SambaGNN space
        device:        torch device for tensors (default: cpu)
        sim_threshold: cosine sim floor for explicit adjacency (default 0.65)
    """

    def __init__(
        self,
        library:       "Library",
        projection:    CLAPProjection,
        device:        None = None,
        sim_threshold: float = DEFAULT_SIM_THRESHOLD,
    ) -> None:
        self._library       = library
        self._projection    = projection
        self._sim_threshold = sim_threshold
        self._snapshot:     Optional[PhiGraphSnapshot] = None

    # ── build ─────────────────────────────────────────────────────────────────

    def build(self) -> PhiGraphSnapshot:
        """
        Project all CLAP-annotated tracks into H and cache the snapshot.

        Tracks without CLAP embeddings are silently excluded from H; they
        appear in missing_tracks() and coverage_report() so callers can decide
        whether to run CLAPModel on them first.

        Returns:
            PhiGraphSnapshot with H (N, d_model), paths, and coverage stats
        """
        H, paths = self._projection.project_library(self._library)

        n_tracks   = self._library.size
        n_embedded = len(paths)
        n_missing  = n_tracks - n_embedded

        if n_missing > 0:
            logger.debug(
                "PhiGraph.build: %d/%d tracks lack CLAP embeddings — run CLAPModel first",
                n_missing,
                n_tracks,
            )

        self._snapshot = PhiGraphSnapshot(
            H=H,
            paths=paths,
            n_tracks=n_tracks,
            n_embedded=n_embedded,
            n_missing=n_missing,
            sim_threshold=self._sim_threshold,
        )
        logger.debug("PhiGraph built: %s", self._snapshot.summary())
        return self._snapshot

    @property
    def snapshot(self) -> PhiGraphSnapshot:
        """Last built snapshot. Raises RuntimeError if build() has not been called."""
        if self._snapshot is None:
            raise RuntimeError("Call PhiGraph.build() before accessing snapshot.")
        return self._snapshot

    # ── adjacency (optional) ──────────────────────────────────────────────────

    def adjacency(
        self,
        threshold: Optional[float] = None,
        snap:      Optional[PhiGraphSnapshot] = None,
    ) -> np.ndarray:
        """
        Build an explicit (N, N) float adjacency matrix from cosine similarity.

        Required only for OctopusTracer's full regression mode
        (soft_edge_mode=False).  In the default soft_edge_mode the tracer
        derives soft edges from H on-the-fly — do not call this unnecessarily
        as it is O(N²) in both time and memory.

        Args:
            threshold: cosine similarity floor for an edge (default sim_threshold)
            snap:      snapshot to operate on (default: last built)

        Returns:
            adj: (N, N) float32 array — 1.0 where sim >= threshold, diagonal zeroed
        """
        snap      = snap or self.snapshot
        threshold = threshold if threshold is not None else self._sim_threshold
        norms     = np.linalg.norm(snap.H, axis=1, keepdims=True)
        H_norm    = snap.H / np.where(norms == 0, 1.0, norms)  # (N, D)
        sim       = (H_norm @ H_norm.T).astype(np.float32)     # (N, N)
        adj       = (sim >= threshold).astype(np.float32)
        np.fill_diagonal(adj, 0.0)
        snap._adj = adj
        return adj

    # ── diagnostics ───────────────────────────────────────────────────────────

    def coverage_report(self) -> dict:
        """Coverage summary dict — suitable for logging and MCP reporting."""
        return self.snapshot.summary()

    def missing_tracks(self) -> list[str]:
        """Tracks in the library with no CLAP embedding — cannot be graphed yet."""
        embedded = set(self.snapshot.paths)
        return [p for p in self._library.playlist if p not in embedded]
