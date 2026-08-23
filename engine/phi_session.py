"""
PhiTracerSession — wires PhiGraph to TracerDaemon.

Data flow:

    PhiLibrary  ──scan──►  Track[]
                                │
    MetadataEncoder / CLAP.npy  │
                                ▼
    CLAPProjection(512→256) ──► snap.H  (N, 256)
                                │
    TagJaccard adjacency ─────► snap.A  (N, N)
                                │
                     run_once(A=snap.A, X=snap.H)
                                │
                          SSMCore.tick(X)         ← SSM transforms snap.H → H_ssm
                                │
                          compute_R(A, H, tau)    ← regression pipeline
                                │
                          OctopusArms.forward(R)  ← 8 MLP arms
                                │
                     ◄──── TracerSummary ──────►  CAIRRNBridge → HarmonicIndex

Snapshot lifecycle:
    - `build()` rescans the library and recomputes H, A.
      Cheap to call infrequently; expensive for 372-track library (~0.5s).
    - `tick()` reuses the current snapshot and does one daemon tick.
      Call in a loop (2Hz or slower — SSM is stateful).
    - `refresh_and_tick()` rebuilds then ticks; call when library changes.

TracerDaemon is constructed with:
    d               = 256   (matches CLAPProjection D_OUT)
    max_tracers     = 8
    tick_gate_interval = 4
    coherence_tau   = 10.0
    vault_root      = None  (no vault writes unless explicitly set)

Usage (one-shot):

    session = make_phi_session()
    session.build()
    summary = session.tick()

Usage (loop):

    session = make_phi_session()
    session.build()
    for _ in range(100):
        summary = session.tick()
        print(summary.arm_sprout, summary.mean_coherence)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from engine.tracer_daemon import TracerDaemon, TracerSummary
from phi.graph.phi_graph import PhiGraph, PhiGraphSnapshot
from phi.library import LIBRARY_ROOT
from phi.models.gemini_clipper import ClipResult, GeminiClipper


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class PhiTracerSession:
    """
    Thin adapter: feeds PhiGraph snapshots into TracerDaemon.

    Parameters
    ----------
    phi_graph : PhiGraph
        Pre-constructed graph (call build() to populate).
    daemon    : TracerDaemon
        Pre-constructed daemon.
    """

    def __init__(
        self,
        phi_graph: PhiGraph,
        daemon: TracerDaemon,
    ) -> None:
        self.phi_graph = phi_graph
        self.daemon = daemon
        self._snap: Optional[PhiGraphSnapshot] = None
        self._clipper: Optional[GeminiClipper] = None

    # ------------------------------------------------------------------
    # Graph lifecycle
    # ------------------------------------------------------------------

    def build(self) -> PhiGraphSnapshot:
        """
        Scan the library and compute H, A.

        Returns the new snapshot. Safe to call repeatedly —
        each call rescans and rebuilds from scratch.
        """
        self._snap = self.phi_graph.build()
        return self._snap

    @property
    def snapshot(self) -> Optional[PhiGraphSnapshot]:
        return self._snap

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------

    def tick(self) -> TracerSummary:
        """
        One TracerDaemon tick using the current snapshot.

        Raises RuntimeError if build() has not been called yet.
        """
        if self._snap is None:
            raise RuntimeError(
                "PhiTracerSession: call build() before tick()."
            )
        return self.daemon.run_once(
            A=self._snap.A,
            X=self._snap.H,
        )

    def refresh_and_tick(self) -> TracerSummary:
        """
        Rebuild the graph then tick.

        Use when tracks have been added/removed from the library.
        Slightly expensive (~0.5s for 372 tracks).
        """
        self.build()
        return self.tick()

    # ------------------------------------------------------------------
    # Clip
    # ------------------------------------------------------------------

    def clip(
        self,
        query: str,
        top_k: int = 5,
        alpha: float = 0.5,
    ) -> ClipResult:
        """
        Clip the top-K tracks from the current snapshot most relevant to query.

        Uses a lazy GeminiClipper backed by the same CLAPProjection and
        MetadataEncoder that built snap.H. Raises RuntimeError if build()
        has not been called.

        Parameters
        ----------
        query : free-text search string (e.g. "dark ambient techno")
        top_k : number of tracks to return (default 5)
        alpha : blend weight — 0.0 pure TF-IDF, 1.0 pure H-space (default 0.5)
        """
        if self._snap is None:
            raise RuntimeError(
                "PhiTracerSession: call build() before clip()."
            )
        alpha_clipped = float(np.clip(alpha, 0.0, 1.0))
        if (
            self._clipper is None
            or self._clipper.top_k != top_k
            or self._clipper.alpha != alpha_clipped
        ):
            self._clipper = GeminiClipper(
                proj=self.phi_graph._proj,
                encoder=self.phi_graph._encoder,
                top_k=top_k,
                alpha=alpha,
            )
        return self._clipper.clip(query, self._snap)

    # ------------------------------------------------------------------
    # Convenience pass-throughs
    # ------------------------------------------------------------------

    @property
    def harmonic_index(self):
        return self.daemon.harmonic_index

    @property
    def bridge(self):
        return self.daemon.bridge

    @property
    def daemon_tick(self) -> int:
        return self.daemon.tick

    @property
    def n_tracks(self) -> int:
        return self._snap.N if self._snap is not None else 0

    @property
    def n_tracers(self) -> int:
        return len(self.daemon.tracers)

    def __repr__(self) -> str:
        return (
            f"<PhiTracerSession "
            f"tracks={self.n_tracks} "
            f"daemon_tick={self.daemon_tick} "
            f"tracers={self.n_tracers} "
            f"clipper={'ready' if self._clipper else 'none'}>"
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_phi_session(
    library_root: Path = LIBRARY_ROOT,
    edge_threshold: float = 0.10,
    max_tracers: int = 8,
    tick_gate_interval: int = 4,
    coherence_tau: float = 10.0,
    vault_root: Optional[Path] = None,
    rng: Optional[np.random.Generator] = None,
) -> PhiTracerSession:
    """
    Construct a PhiTracerSession with sensible defaults.

    Parameters
    ----------
    library_root      : path to Liked Songs library
    edge_threshold    : Jaccard threshold for graph edges (default 0.10)
    max_tracers       : TracerDaemon max concurrent tracers (default 8)
    tick_gate_interval: spawn a tracer every N ticks (default 4)
    coherence_tau     : CAIRRN coherence decay constant (default 10.0)
    vault_root        : if set, SambaWriter writes arm outputs to vault
    rng               : optional numpy Generator for reproducibility

    Returns
    -------
    PhiTracerSession  (build() not yet called — call it before tick())
    """
    phi_graph = PhiGraph(
        library_root=library_root,
        edge_threshold=edge_threshold,
        rng=rng,
    )
    daemon = TracerDaemon(
        max_tracers=max_tracers,
        tick_gate_interval=tick_gate_interval,
        d=256,                          # matches CLAPProjection D_OUT
        coherence_tau=coherence_tau,
        vault_root=vault_root,
    )
    return PhiTracerSession(phi_graph=phi_graph, daemon=daemon)
