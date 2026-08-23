"""
Stage II Query Router for the Gemini Clipper architecture.

Lightweight TF-IDF centroid classifier that intercepts a query and decides
whether to route to semantic search (SEARCH) or bypass entirely (PASSTHROUGH).

Outputs:
    cluster_id  — which semantic partition to search (0-based)
    action      — RouteAction.SEARCH or RouteAction.PASSTHROUGH
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from psspps.scorer import build_tfidf, query_vector, semantic_scores, tokenize

__all__ = [
    "RouteAction",
    "RouteDecision",
    "QueryRouter",
]


class RouteAction(str, Enum):
    SEARCH = "SEARCH"
    PASSTHROUGH = "PASSTHROUGH"


@dataclass
class RouteDecision:
    action: RouteAction
    cluster_id: int       # 0-based cluster index; -1 if PASSTHROUGH
    confidence: float     # ∈ [0, 1]
    query_tokens: list[str] = field(default_factory=list)


class QueryRouter:
    """
    Lightweight query classifier for the Gemini Clipper Stage II.

    Fits a TF-IDF centroid model over the track corpus at construction
    time. At route time, it classifies the query into the nearest centroid
    (cluster_id) and decides SEARCH vs PASSTHROUGH.

    Parameters
    ----------
    n_clusters   : number of semantic clusters (default 8 — matches harmonic shards)
    min_tokens   : queries with fewer tokens than this → PASSTHROUGH (default 2)
    min_score    : TF-IDF cosine score below this → PASSTHROUGH (default 0.05)
    """

    def __init__(
        self,
        n_clusters: int = 8,
        min_tokens: int = 2,
        min_score: float = 0.05,
    ) -> None:
        self.n_clusters = n_clusters
        self.min_tokens = min_tokens
        self.min_score = float(min_score)

        self._vocab: list[str] | None = None
        self._centroids: np.ndarray | None = None  # (n_clusters, n_terms)

    # ------------------------------------------------------------------
    # Fitting
    # ------------------------------------------------------------------

    def fit(self, corpus: list[str]) -> None:
        """
        Fit the router on a list of text documents (track text strings).

        Builds TF-IDF matrix, then computes n_clusters centroids via Lloyd's
        algorithm (iterative k-means, max 20 iterations).  Centroids are
        L2-normalised for cosine distance.

        Seeding uses the k-means++ heuristic: pick the first centroid at
        random, then pick each successive centroid proportional to the squared
        cosine distance from the nearest already-chosen centroid.  This gives
        far better initial separation than pure random placement.
        """
        tfidf, vocab = build_tfidf(corpus)  # (n_docs, n_terms), L2-normalised rows
        self._vocab = vocab

        n_docs, n_terms = tfidf.shape
        centroids = np.zeros((self.n_clusters, n_terms), dtype=float)

        if n_docs == 0:
            self._centroids = centroids
            return

        k = min(self.n_clusters, n_docs)   # can't have more clusters than docs

        # ── k-means++ seeding ─────────────────────────────────────────────────
        rng = np.random.default_rng(42)
        chosen: list[int] = [int(rng.integers(n_docs))]
        for _ in range(k - 1):
            # squared cosine distance from each doc to its nearest chosen centroid
            # tfidf rows are L2-normalised → cosine sim = dot product
            sims = tfidf[chosen] @ tfidf.T      # (len(chosen), n_docs)
            nearest_sim = sims.max(axis=0)       # (n_docs,)
            sq_dist = np.maximum(0.0, 1.0 - nearest_sim) ** 2
            sq_dist_sum = sq_dist.sum()
            if sq_dist_sum <= 0.0:
                break
            probs = sq_dist / sq_dist_sum
            chosen.append(int(rng.choice(n_docs, p=probs)))

        centroids[:k] = tfidf[chosen]

        # ── Lloyd iteration ───────────────────────────────────────────────────
        _MAX_ITER = 20
        for _iter in range(_MAX_ITER):
            # Assignment: each doc → nearest centroid by cosine similarity
            sims    = tfidf @ centroids[:k].T    # (n_docs, k)
            assigns = np.argmax(sims, axis=1)    # (n_docs,)

            new_centroids = np.zeros_like(centroids[:k])
            changed = False
            for ci in range(k):
                members = np.where(assigns == ci)[0]
                if members.size == 0:
                    # Empty cluster: reinitialise to a random doc
                    new_centroids[ci] = tfidf[int(rng.integers(n_docs))]
                    changed = True
                else:
                    mean_vec = tfidf[members].mean(axis=0)
                    norm = np.linalg.norm(mean_vec)
                    new_centroids[ci] = mean_vec / norm if norm > 1e-12 else mean_vec
                    if not np.allclose(new_centroids[ci], centroids[ci], atol=1e-6):
                        changed = True

            centroids[:k] = new_centroids
            if not changed:
                break   # converged

        self._centroids = centroids

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def route(self, query: str) -> RouteDecision:
        """
        Classify a query string.

        Steps:
        1. Tokenize the query.
        2. If token count < min_tokens → PASSTHROUGH (cluster_id=-1, confidence=0).
        3. Build query TF-IDF vector.
        4. Cosine similarity against each cluster centroid.
        5. Best centroid score < min_score → PASSTHROUGH.
        6. Else → SEARCH with cluster_id = argmax centroid sim, confidence = max sim.

        Returns RouteDecision.
        """
        if not self.is_fitted:
            raise RuntimeError(
                "QueryRouter.route() called before fit(). Call fit(corpus) first."
            )

        tokens = tokenize(query)

        if len(tokens) < self.min_tokens:
            return RouteDecision(
                action=RouteAction.PASSTHROUGH,
                cluster_id=-1,
                confidence=0.0,
                query_tokens=tokens,
            )

        q_vec = query_vector(query, self._vocab)  # (n_terms,) L2-normalised

        # Cosine similarity: centroids are already L2-normalised, q_vec is too
        # → sim = dot product
        sims = self._centroids @ q_vec  # (n_clusters,)
        sims = np.nan_to_num(sims, nan=0.0)

        best_idx = int(np.argmax(sims))
        best_score = float(sims[best_idx])

        if best_score < self.min_score:
            return RouteDecision(
                action=RouteAction.PASSTHROUGH,
                cluster_id=-1,
                confidence=float(np.clip(best_score, 0.0, 1.0)),
                query_tokens=tokens,
            )

        return RouteDecision(
            action=RouteAction.SEARCH,
            cluster_id=best_idx,
            confidence=float(np.clip(best_score, 0.0, 1.0)),
            query_tokens=tokens,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_fitted(self) -> bool:
        return self._centroids is not None and self._vocab is not None

    def __repr__(self) -> str:
        fitted = "fitted" if self.is_fitted else "unfitted"
        return (
            f"<QueryRouter n_clusters={self.n_clusters} "
            f"min_tokens={self.min_tokens} min_score={self.min_score} [{fitted}]>"
        )
