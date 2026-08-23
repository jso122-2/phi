# -*- coding: utf-8 -*-
"""phi.models.meta_clipper — per-track metadata embedding for the D4 pipeline.

Pipeline
--------

    text  (title + artist + album + genre — lowercased, concatenated)
      │
      ▼
    TF-IDF(max_features=5 000, ngram_range=(1,2), sublinear_tf=True)
      │   sparse (N, V)
      ▼
    TruncatedSVD(n_components=36) + L2 row-norm
      │   dense (N, 36)   →  clipper_emb  ← fed into D4XGBoostModel
      ▼
    PCA(n_components=2)
      │
    MinMaxScaler → [0.02, 0.98]²
      │   (N, 2)  →  clipper_x, clipper_y  ← track's position on the curve
      ▼
    DragonCurve.fold_bits + score_b  →  fold_bits (8-d), d4_b

The 45-d XGBoost feature vector is: clipper_emb(36) + fold_bits(8) + d4_b(1).

Typical usage
-------------
    # Training: fit on the full library corpus first, then batch-transform
    clipper = MetaClipper(depth=8)
    clipper.fit(all_items)                        # corpus-wide vocabulary
    anns, rolling = clipper.run_batch(all_items)  # deterministic positions
    model.fit(anns, rolling)

    # Scripted per-batch (legacy train_d4.py pattern):
    clipper = MetaClipper(depth=8)
    clipper.fit(all_items)                        # call once before the loop
    for batch in batches:
        anns, _ = clipper.run_batch(batch)

    # Inference: load a frozen pipeline
    clipper = MetaClipper.load("~/.phi/meta_clipper.joblib")
    anns, _ = clipper.run_batch([(path, meta)])

Notes
-----
- `device` is accepted but ignored — the pipeline is pure numpy / sklearn.
- For batches smaller than n_components SVD is clamped to n_samples−1 and
  the missing dimensions are zero-padded to preserve the fixed 36-d shape.
- The PCA + MinMaxScaler is fitted to the *training corpus* and frozen;
  new tracks at inference time are projected into the same 2-D space.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MinMaxScaler, normalize

from phi.models.base import PhiModel
from phi.models.dragon_curve import DragonCurve

logger = logging.getLogger(__name__)

__all__ = ["MetaClipper", "MetaClipperModel"]

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_EMB_DIM:      int = 36        # clipper_emb width — matches D4XGBoostModel._EMB_DIM
_MAX_FEATURES: int = 5_000     # TF-IDF vocabulary cap
_NGRAM_RANGE         = (1, 2)  # unigrams + bigrams
_SCALE_MARGIN: float = 0.02    # [margin, 1−margin]² to keep dots off the edge


# ─────────────────────────────────────────────────────────────────────────────
# Text helper
# ─────────────────────────────────────────────────────────────────────────────

def _meta_to_text(meta: dict) -> str:
    """
    Flatten a track meta dict into one lowercased text document.

    Reads: title, artist, album, genre.  Unknown fields are silently skipped.
    """
    parts = [
        meta.get("title")  or "",
        meta.get("artist") or "",
        meta.get("album")  or "",
        meta.get("genre")  or "",
    ]
    return " ".join(p.strip() for p in parts if p).lower()


# ─────────────────────────────────────────────────────────────────────────────
# MetaClipper
# ─────────────────────────────────────────────────────────────────────────────

class MetaClipper:
    """
    Per-track metadata → dragon curve feature extractor.

    Implements the ``run_batch()`` interface expected by train_d4.py and
    D4XGBoostModel.  All computation is CPU-only (pure numpy + sklearn).

    Args:
        depth:        dragon curve fold depth (default 8 → 256 segments,
                      8-bit fold vectors)
        device:       ignored — accepted for API compatibility with train_d4.py
        n_components: SVD latent dimensions = clipper_emb width (default 36)
    """

    def __init__(
        self,
        depth:        int = 8,
        device:       str = "cpu",   # API compat — not used
        n_components: int = _EMB_DIM,
    ) -> None:
        self.depth        = depth
        self.n_components = n_components
        self._dc          = DragonCurve(depth=depth)

        self._vec:    Optional[TfidfVectorizer] = None
        self._svd:    Optional[TruncatedSVD]    = None
        self._pca:    Optional[PCA]             = None
        self._scaler: Optional[MinMaxScaler]    = None
        self._fitted: bool                      = False
        self._n_svd_actual: int                 = 0   # ≤ n_components after fit

    # ── corpus helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _texts(items: list[tuple[str, dict]]) -> list[str]:
        return [_meta_to_text(meta) for _, meta in items]

    # ── fit ───────────────────────────────────────────────────────────────────

    def fit(self, items: list[tuple[str, dict]]) -> "MetaClipper":
        """
        Fit the TF-IDF → SVD → PCA → scaler pipeline on a corpus.

        Must be called before :meth:`transform` or :meth:`run_batch`.
        Safe to re-call (re-fits from scratch, discarding prior state).

        Args:
            items: list of (path, meta_dict) — all tracks in the library

        Returns:
            self (for chaining)
        """
        texts = self._texts(items)
        N     = len(texts)
        if N < 3:
            raise ValueError(
                f"MetaClipper.fit needs ≥ 3 items, got {N}"
            )

        # TF-IDF ──────────────────────────────────────────────────────────────
        self._vec = TfidfVectorizer(
            max_features=_MAX_FEATURES,
            ngram_range=_NGRAM_RANGE,
            sublinear_tf=True,
            strip_accents="unicode",
            min_df=1,
        )
        X_tfidf = self._vec.fit_transform(texts)   # sparse (N, V)

        # TruncatedSVD — clamp to n_samples−1 for small corpora ───────────────
        n_svd = min(self.n_components, N - 1)
        self._n_svd_actual = n_svd

        self._svd = TruncatedSVD(n_components=n_svd, random_state=42, n_iter=5)
        X_svd     = self._svd.fit_transform(X_tfidf)          # (N, n_svd)
        X_svd     = normalize(X_svd.astype(np.float64), norm="l2")

        var_ratio = float(self._svd.explained_variance_ratio_.sum())
        logger.info(
            "MetaClipper.fit: N=%d  vocab=%d  n_svd=%d  explained_var=%.3f",
            N, X_tfidf.shape[1], n_svd, var_ratio,
        )

        # PCA 36→2 (uses only the actual n_svd columns) ───────────────────────
        n_pca    = min(2, n_svd)
        self._pca = PCA(n_components=n_pca, random_state=42)
        X_pca     = self._pca.fit_transform(X_svd)             # (N, n_pca)

        # If n_pca == 1 (degenerate corpus), duplicate the single axis
        if n_pca == 1:
            X_pca = np.hstack([X_pca, X_pca])

        # MinMaxScaler with small margins so no point sits exactly on the edge
        self._scaler = MinMaxScaler(
            feature_range=(_SCALE_MARGIN, 1.0 - _SCALE_MARGIN)
        )
        self._scaler.fit(X_pca)

        self._fitted = True
        return self

    # ── transform ────────────────────────────────────────────────────────────

    def transform(
        self,
        items: list[tuple[str, dict]],
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Project items through the fitted pipeline.

        Args:
            items: list of (path, meta_dict)

        Returns:
            emb:  ndarray (N, 36) float32 — L2-normalised SVD embedding
                  (clipper_emb)
            xy:   ndarray (N, 2)  float64 — (clipper_x, clipper_y) ∈ [0, 1]²
        """
        if not self._fitted:
            raise RuntimeError("MetaClipper not fitted — call fit() first")

        texts   = self._texts(items)
        N       = len(texts)

        # TF-IDF → SVD → L2-norm
        X_tfidf  = self._vec.transform(texts)                    # sparse (N, V)
        X_svd    = self._svd.transform(X_tfidf)                  # (N, n_svd)
        X_svd    = normalize(X_svd.astype(np.float64), norm="l2")

        # Build emb: zero-pad if n_svd < n_components
        emb = np.zeros((N, self.n_components), dtype=np.float32)
        emb[:, :self._n_svd_actual] = X_svd.astype(np.float32)

        # PCA → scaler → xy
        X_pca = self._pca.transform(X_svd)                       # (N, n_pca)
        if X_pca.shape[1] == 1:
            X_pca = np.hstack([X_pca, X_pca])
        xy = np.clip(
            self._scaler.transform(X_pca),
            0.0, 1.0,
        ).astype(np.float64)                                      # (N, 2)

        return emb, xy

    # ── run_batch ────────────────────────────────────────────────────────────

    def run_batch(
        self,
        items:          list[tuple[str, dict]],
        rolling_window: int = 16,
    ) -> tuple[list[dict], np.ndarray]:
        """
        Produce annotation dicts + rolling D4_A for a list of tracks.

        If not yet fitted, auto-fits on this batch first (vocabulary is limited
        to this batch — call fit(all_items) beforehand for better coverage).

        Args:
            items:          list of (path, meta_dict) pairs
            rolling_window: causal rolling-mean window for D4_A

        Returns:
            annotations: list[dict] — one per item, keys:
                ``clipper_emb``  list[float]  len=36
                ``clipper_x``    float ∈ [0, 1]
                ``clipper_y``    float ∈ [0, 1]
                ``fold_bits``    list[float]  len=depth
                ``d4_b``         float
            rolling_d4a: ndarray (N,) — causal rolling mean of D4_A at each
                         track's (clipper_x, clipper_y) position on the curve
        """
        if not self._fitted:
            logger.warning(
                "MetaClipper.run_batch: not fitted — auto-fitting on batch "
                "(N=%d).  Call fit(all_items) first for corpus-wide vocab.",
                len(items),
            )
            self.fit(items)

        emb, xy = self.transform(items)   # (N, 36), (N, 2)
        N       = len(items)

        annotations: list[dict] = []
        for i in range(N):
            x_n = float(xy[i, 0])
            y_n = float(xy[i, 1])

            cx, cy      = self._dc.unit_to_curve(x_n, y_n)
            seg         = self._dc.nearest_segment(cx, cy)
            D1, D2, D3  = self._dc.d1_d2_d3(seg)
            d4_b        = self._dc.score_b(D1, D2, D3)
            bits        = self._dc.fold_bits(seg)

            annotations.append({
                "clipper_emb": emb[i].tolist(),
                "clipper_x":   x_n,
                "clipper_y":   y_n,
                "fold_bits":   bits.tolist(),
                "d4_b":        float(d4_b),
            })

        rolling_d4a = self._dc.rolling_d4_a(
            xy, window=rolling_window, normalized=True
        )
        return annotations, rolling_d4a

    # ── persistence ───────────────────────────────────────────────────────────

    def save(self, path: str | Path) -> None:
        """Serialize the fitted pipeline to a joblib file."""
        try:
            import joblib
        except ImportError as exc:
            raise ImportError("joblib is required: pip install joblib") from exc
        if not self._fitted:
            raise RuntimeError("Cannot save: MetaClipper not fitted")
        payload = {
            "vec":          self._vec,
            "svd":          self._svd,
            "pca":          self._pca,
            "scaler":       self._scaler,
            "depth":        self.depth,
            "n_components": self.n_components,
            "n_svd_actual": self._n_svd_actual,
        }
        import joblib
        joblib.dump(payload, path)
        logger.info("MetaClipper saved → %s", path)

    @classmethod
    def load(cls, path: str | Path) -> "MetaClipper":
        """Load a previously saved pipeline."""
        try:
            import joblib
        except ImportError as exc:
            raise ImportError("joblib is required: pip install joblib") from exc
        import joblib
        payload    = joblib.load(path)
        inst       = cls(depth=payload["depth"], n_components=payload["n_components"])
        inst._vec  = payload["vec"]
        inst._svd  = payload["svd"]
        inst._pca  = payload["pca"]
        inst._scaler      = payload["scaler"]
        inst._n_svd_actual = payload.get("n_svd_actual", payload["n_components"])
        inst._fitted = True
        logger.info("MetaClipper loaded ← %s", path)
        return inst

    def __repr__(self) -> str:
        status = f"fitted n_svd={self._n_svd_actual}" if self._fitted else "not fitted"
        return f"<MetaClipper depth={self.depth} n_components={self.n_components} {status}>"


class MetaClipperModel(PhiModel):
    """PhiModel wrapper: fitted MetaClipper → clipper_emb / fold_bits / d4_b."""

    name        = "meta_clipper"
    version     = "1.0.0"
    description = "TF-IDF SVD clipper + dragon-curve fold bits (feeds D4XGBoostModel)"

    def __init__(self, clipper: MetaClipper | None = None) -> None:
        self._clipper = clipper

    def can_process(self, path: str, meta: dict) -> bool:
        return (
            self._clipper is not None
            and self._clipper._fitted
            and meta.get("clipper_emb") is None
        )

    def run(self, path: str, meta: dict) -> dict:
        if self._clipper is None or not self._clipper._fitted:
            return {}
        try:
            anns, _ = self._clipper.run_batch([(path, meta)])
        except Exception as exc:
            logger.warning("MetaClipperModel.run(%s) failed: %s", path, exc)
            return {}
        return anns[0] if anns else {}
