"""phi.graph._snapshot — PhiGraphSnapshot immutable snapshot type."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from phi._track import Track

if TYPE_CHECKING:
    from phi.metadata.schema import SongNode


@dataclass
class PhiGraphSnapshot:
    """
    Immutable snapshot of the PhiGraph at one point in time.

    Parameters
    ----------
    tracks  : ordered list of Track (index = node index)
    H       : (N, 256) float64 — projected embeddings
    A       : (N, N)   float64 — binary adjacency (tag-Jaccard)
    """
    tracks: list[Track]
    H: np.ndarray   # (N, 256)
    A: np.ndarray   # (N, N)

    def paths(self) -> list[Path]:
        """Audio path for every node."""
        return [t.path for t in self.tracks]

    def index_of(self, track: Track) -> int:
        """Node index of a track (-1 if not found)."""
        for i, t in enumerate(self.tracks):
            if t.path == track.path:
                return i
        return -1

    def path_of(self, idx: int) -> Path:
        """Audio path for node at index idx."""
        return self.tracks[idx].path

    def top_k_similar(self, idx: int, k: int = 5) -> list[int]:
        """
        k nearest neighbours of node idx by cosine similarity on H.

        Returns sorted indices (most similar first), excluding idx.
        """
        h = self.H
        n = h.shape[0]
        if n == 0:
            return []
        query = h[idx]
        q_norm = np.linalg.norm(query)
        if q_norm < 1e-12:
            return []
        norms = np.linalg.norm(h, axis=1)
        norms = np.where(norms < 1e-12, 1e-12, norms)
        sims = (h @ query) / (norms * q_norm)
        sims[idx] = -1.0
        k = min(k, n - 1)
        return list(np.argsort(sims)[::-1][:k].tolist())

    def window(self, indices: list[int]) -> list["SongNode"]:
        """Extract a ≤6-node SongNode window from this snapshot.

        Parameters
        ----------
        indices : global node indices into self.tracks, length ≤ WINDOW_SIZE (6)

        Returns
        -------
        list[SongNode]
            One SongNode per index.  Fields populated:
              position.node_id  — window-local index (0-based within slice)
              position.shard    — CAIRRN shard from _SHARD_MAP
              position.degree   — row-sum of sub-adjacency A[indices][:,indices]
              position.h_u      — H[global_idx] from this snapshot (256-d)
              audio             — AudioFeatures zeroed (librosa not re-run here)

        Raises
        ------
        ValueError if len(indices) > WINDOW_SIZE or any index out of range
        """
        from phi.metadata.node_builder import update_degrees
        from phi.metadata.schema import (
            AudioFeatures,
            GraphPosition,
            SongNode,
            WINDOW_SIZE,
            _SHARD_MAP,
        )

        if len(indices) > WINDOW_SIZE:
            raise ValueError(
                f"Window size is fixed at {WINDOW_SIZE}; got {len(indices)} indices."
            )
        for i in indices:
            if not (0 <= i < self.N):
                raise ValueError(f"Index {i} out of range for snapshot of size {self.N}.")

        A_sub = self.A[np.ix_(indices, indices)]

        nodes: list[SongNode] = []
        for window_id, global_idx in enumerate(indices):
            h_vec: list[float] = self.H[global_idx].tolist()
            position = GraphPosition(
                node_id=window_id,
                shard=_SHARD_MAP[window_id],
                h_u=h_vec,
            )
            nodes.append(
                SongNode(
                    track=self.tracks[global_idx],
                    audio=AudioFeatures(),
                    position=position,
                )
            )

        update_degrees(nodes, A_sub)
        return nodes

    @property
    def N(self) -> int:
        return len(self.tracks)

    def __repr__(self) -> str:
        return f"<PhiGraphSnapshot N={self.N} H={self.H.shape}>"
