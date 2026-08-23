"""
PhiGraph — Phi Library graph → H ∈ ℝ^(N×256) for OctopusTracer.

Architecture (LOCKED — CLAPProjection and PhiGraph agent-log):

    PhiGraph wraps a PhiLibrary and a CLAPProjection to produce
    H ∈ ℝ^(N_tracks × 256) — the direct input for OctopusTracer.

    It mirrors the TopologicalGraph contract:
      build()      safe to call repeatedly
      adjacency()  on-demand (soft_edge_mode doesn't need it)

Adjacency (A ∈ {0,1}^(N×N)):
    Edge (u, v) when Jaccard(tags_u, tags_v) > edge_threshold.
    Diagonal always 0.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from phi.graph._adjacency import _tag_adjacency
from phi.graph._snapshot import PhiGraphSnapshot
from phi.library import LIBRARY_ROOT, PhiLibrary
from phi.models.clap_proj import CLAPProjection, MetadataEncoder, embed_tracks
from phi.metadata.schema import SongNode

__all__ = ["PhiGraph", "PhiGraphSnapshot", "SongNode", "_tag_adjacency"]


class PhiGraph:
    """
    Builds H and A from a PhiLibrary.

    Parameters
    ----------
    library_root    : path to the Liked Songs library (default: LIBRARY_ROOT)
    edge_threshold  : Jaccard(tags_u, tags_v) > this → edge in A (default 0.10)
    tag_vocab_top_k : number of lfm_tags to include in MetadataEncoder vocab
    rng             : optional Generator for CLAPProjection init
    """

    def __init__(
        self,
        library_root: Path = LIBRARY_ROOT,
        edge_threshold: float = 0.10,
        tag_vocab_top_k: int = 256,
        rng: Optional[np.random.Generator] = None,
    ) -> None:
        self.library_root = Path(library_root)
        self.edge_threshold = edge_threshold
        self.tag_vocab_top_k = tag_vocab_top_k
        self._library = PhiLibrary(library_root=self.library_root)
        self._proj = CLAPProjection.load_default(rng=rng)
        self._encoder = MetadataEncoder()
        self._snapshot: Optional[PhiGraphSnapshot] = None

    def build(self, annotations: dict[str, dict] | None = None) -> PhiGraphSnapshot:
        """
        Scan the library, encode tracks, build H and A.

        Parameters
        ----------
        annotations : optional {path: ann_dict} mapping from Library.annotations.
                      When supplied, consensus dims [273:284] of each metadata
                      vector are filled (valence, energy, BPM, mood, buoyancy).

        Returns
        -------
        PhiGraphSnapshot
        """
        tracks = self._library.tracks
        vocab = self._library.tag_vocabulary(top_k=self.tag_vocab_top_k)
        self._encoder.set_vocab(vocab)
        X = embed_tracks(tracks, self._proj, self._encoder, annotations=annotations)
        H = self._proj.forward(X)                              # (N, 256)
        A = _tag_adjacency(tracks, self.edge_threshold)
        self._snapshot = PhiGraphSnapshot(tracks=tracks, H=H, A=A)
        return self._snapshot

    def adjacency(self) -> np.ndarray:
        """Return the (N, N) adjacency matrix; builds if needed."""
        if self._snapshot is None:
            self.build()
        return self._snapshot.A

    def window(self, indices: list[int]) -> list[SongNode]:
        """Extract a ≤6-node SongNode window; builds the snapshot if needed.

        Parameters
        ----------
        indices : global node indices into the library track list, length ≤ 6

        Returns
        -------
        list[SongNode] — see PhiGraphSnapshot.window() for full field docs
        """
        if self._snapshot is None:
            self.build()
        return self._snapshot.window(indices)

    @property
    def snapshot(self) -> Optional[PhiGraphSnapshot]:
        return self._snapshot

    @property
    def library(self) -> PhiLibrary:
        return self._library

    @property
    def proj(self) -> CLAPProjection:
        return self._proj

    def __repr__(self) -> str:
        built = self._snapshot is not None
        n = self._snapshot.N if built else "?"
        return f"<PhiGraph built={built} N={n} threshold={self.edge_threshold}>"
