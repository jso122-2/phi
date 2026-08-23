"""phi.graph._adjacency — tag-Jaccard binary adjacency builder."""
from __future__ import annotations

import numpy as np

from phi._track import Track


def _tag_adjacency(tracks: list[Track], threshold: float) -> np.ndarray:
    """
    Build binary (N, N) adjacency where A[u, v] = 1 iff
    Jaccard(tags_u, tags_v) > threshold.

    Diagonal is 0.  Matrix is symmetric.
    Tags: all_tags (lfm + discogs + itunes, lowercased).
    """
    N = len(tracks)
    tag_sets: list[frozenset[str]] = [
        frozenset(t.lower() for t in tr.all_tags) for tr in tracks
    ]
    A = np.zeros((N, N), dtype=np.float64)
    for u in range(N):
        for v in range(u + 1, N):
            tu, tv = tag_sets[u], tag_sets[v]
            if not tu and not tv:
                continue
            union = len(tu | tv)
            if union > 0 and len(tu & tv) / union > threshold:
                A[u, v] = 1.0
                A[v, u] = 1.0
    return A
