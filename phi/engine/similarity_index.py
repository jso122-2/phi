# -*- coding: utf-8 -*-
"""phi.engine.similarity_index — numpy-accelerated cosine similarity search.

``PhiSimilarityIndex`` builds a precomputed (N × D) float32 matrix over CLAP
vectors and executes O(1) nearest-neighbour queries via a single matrix-vector
multiply.  Falls back gracefully when numpy is unavailable.

Invalidated by the MATH hub: when MATH loses coherence (after ~20 CLAP
annotation batches) the index is rebuilt automatically via the
``bind_floor`` subscription in phi.core.similarity.
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional

logger = logging.getLogger("phi.cairrn")


class PhiSimilarityIndex:
    """Precomputed numpy matrix for O(1) cosine similarity search over CLAP vectors.

    Instead of iterating each track pair in Python (O(n × 512) per query), this
    builds a (n × 512) float32 matrix and does a single matrix-vector multiply::

        scores = matrix @ query_vec      # shape (n,)

    For a 1000-track library this is ~200× faster than the pure-Python path.
    """

    def __init__(self, paths: List[str], matrix, norms) -> None:
        self._paths      = paths
        self._matrix     = matrix
        self._norms      = norms
        self._built_at   = time.monotonic()
        # Build lookup caches eagerly — avoids fragile lazy double-underscore
        # name-mangling and ensures find_similar() never pays the build cost
        # during a hot query.
        self._path_set   = set(paths)
        self._path_to_idx: dict = {p: i for i, p in enumerate(paths)}

    @classmethod
    def build(cls, library) -> "PhiSimilarityIndex | None":
        """Build from library annotations.

        Returns None when numpy is unavailable or fewer than 2 CLAP tracks exist.
        """
        try:
            import numpy as np
        except ImportError:
            return None

        paths: list = []
        vecs:  list = []
        for p in library.playlist:
            ann = library.get_annotation(p)
            if ann is None:
                continue
            v = ann.get("mood_vec")
            if v:
                paths.append(p)
                vecs.append(v)

        if len(paths) < 2:
            return None

        matrix = np.array(vecs, dtype=np.float32)
        norms  = np.linalg.norm(matrix, axis=1)
        norms  = np.where(norms == 0, 1.0, norms)
        matrix = matrix / norms[:, None]

        logger.info(
            "CAIRRN/MATH: similarity index built  tracks=%d  dim=%d",
            len(paths), matrix.shape[1],
        )
        return cls(paths, matrix, norms)

    def find_similar(
        self,
        seed_path: str,
        n: int = 10,
        exclude: Optional[set] = None,
        library=None,
    ) -> List[tuple]:
        """Find the *n* most similar tracks to *seed_path*.

        Returns list of (path, score) sorted by descending similarity.
        """
        try:
            import numpy as np
        except ImportError:
            return []

        exclude = exclude or set()

        if seed_path in self._path_set:
            idx = self._path_to_idx[seed_path]
            q   = self._matrix[idx]
        elif library is not None:
            ann = library.get_annotation(seed_path)
            if not ann:
                return []
            v = ann.get("mood_vec")
            if not v:
                return []
            q = np.array(v, dtype=np.float32)
            norm = np.linalg.norm(q)
            if norm > 0:
                q = q / norm
        else:
            return []

        scores = self._matrix @ q
        results = [
            (p, float(s))
            for p, s in zip(self._paths, scores)
            if p != seed_path and p not in exclude
        ]
        results.sort(key=lambda t: -t[1])
        return results[:n]

    def find_similar_to_vec(
        self,
        vec: List[float],
        n: int = 10,
        exclude: Optional[set] = None,
    ) -> List[tuple]:
        """Find the *n* tracks most similar to a raw embedding vector.

        Returns list of (path, score) sorted by descending similarity.
        """
        try:
            import numpy as np
        except ImportError:
            return []

        exclude = exclude or set()
        q = np.array(vec, dtype=np.float32)
        norm = np.linalg.norm(q)
        if norm > 0:
            q = q / norm

        scores = self._matrix @ q
        results = [
            (p, float(s))
            for p, s in zip(self._paths, scores)
            if p not in exclude
        ]
        results.sort(key=lambda t: -t[1])
        return results[:n]

    @property
    def size(self) -> int:
        """Number of tracks in the index."""
        return len(self._paths)

    @property
    def age_secs(self) -> float:
        """Seconds elapsed since this index was built."""
        return time.monotonic() - self._built_at

