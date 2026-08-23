"""
models.genre_predictor — XGBoost-backed genre predictor for PhiLibrary.

Uses the trained xgb_cluster.json model (k=8 clusters) to assign a genre
label to any Track.  Cluster → genre label is derived from the dominant tag
activation per cluster using the saved X_encoded.npy + labels.npy artifacts.

Lookup order for genre_for(track):
    1. cluster_map.json  (O(1) dict — known tracks from training run)
    2. XGBoost predict   (encode_one → clf.predict for unseen tracks)
    3. cluster_genre()   → human-readable tag-derived label

Artifacts are produced by ``python -m models.metadata_cluster``.
Call ``GenrePredictor.artifacts_ready()`` before constructing — PhiLibrary.by_genre
falls back to tag labels when they are missing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from phi._track import Track
from phi.models._metadata_encoder import MetadataEncoder

if TYPE_CHECKING:
    from phi.library import PhiLibrary

OUT_DIR = Path(__file__).parent / "cluster_out"
_ARTIFACTS = ("xgb_cluster.json", "cluster_map.json", "X_encoded.npy", "labels.npy")

__all__ = ["GenrePredictor", "OUT_DIR"]


class GenrePredictor:
    """
    Predict the genre cluster for any Track using the trained XGBoost model.

    Parameters
    ----------
    lib : PhiLibrary
        Used once at init to rebuild the tag vocabulary that matches training.

    Attributes
    ----------
    genre_labels : dict[int, str]
        Cluster id → dominant-tag genre label (derived at init, not stored on disk).
    """

    @classmethod
    def artifacts_ready(cls) -> bool:
        """True when metadata_cluster artefacts exist and xgboost is importable."""
        if not all((OUT_DIR / name).exists() for name in _ARTIFACTS):
            return False
        try:
            import xgboost  # noqa: F401
        except ImportError:
            return False
        return True

    def __init__(self, lib: PhiLibrary) -> None:
        if not self.artifacts_ready():
            raise FileNotFoundError(
                f"GenrePredictor artefacts missing at {OUT_DIR}. "
                "Run: python -m models.metadata_cluster"
            )

        import xgboost as xgb

        # ── XGBoost model ────────────────────────────────────────────────────
        self._clf = xgb.XGBClassifier()
        self._clf.load_model(str(OUT_DIR / "xgb_cluster.json"))

        # ── cluster_map: display_name → cluster_id (fast path for known tracks)
        with open(OUT_DIR / "cluster_map.json", encoding="utf-8") as fh:
            self._cluster_map: dict[str, int] = json.load(fh)

        # ── MetadataEncoder — same vocab as training ──────────────────────────
        self._enc = MetadataEncoder()
        vocab = lib.tag_vocabulary(top_k=256)
        self._enc.set_vocab(vocab)

        # ── Derive cluster → genre label from saved artifacts ─────────────────
        self.genre_labels: dict[int, str] = self._derive_cluster_labels()

    # ── label derivation ──────────────────────────────────────────────────────

    def _derive_cluster_labels(self) -> dict[int, str]:
        """
        Compute a human-readable label for each cluster by finding the tag
        dimension with the highest mean activation across all tracks in that cluster.

        Falls back to ``cluster_<id>`` when no tag activations are positive.
        """
        X = np.load(OUT_DIR / "X_encoded.npy")     # (N, 512)
        labels = np.load(OUT_DIR / "labels.npy")   # (N,)
        vocab = self._enc._tag_vocab               # list[str], len ≤ 256

        result: dict[int, str] = {}
        for cid in np.unique(labels):
            mask = labels == int(cid)
            cluster_X = X[mask]                    # (n_in_cluster, 512)
            # dims [17 : 17 + |vocab|] are the multi-hot tag activations
            tag_means = cluster_X[:, 17 : 17 + len(vocab)].mean(axis=0)
            if tag_means.max() > 0:
                top_idx = int(np.argmax(tag_means))
                label = vocab[top_idx] if top_idx < len(vocab) else f"cluster_{cid}"
            else:
                label = f"cluster_{cid}"
            result[int(cid)] = label

        return result

    # ── prediction API ────────────────────────────────────────────────────────

    def predict_cluster(self, track: Track) -> int:
        """Encode ``track`` and return the XGBoost-predicted cluster id."""
        vec = self._enc.encode_one(track).reshape(1, -1)
        return int(self._clf.predict(vec)[0])

    def cluster_id_for(self, track: Track) -> int:
        """
        Return cluster id for ``track``.

        Uses cluster_map lookup first (O(1)); falls back to XGBoost prediction
        for tracks not seen during training.
        """
        cid = self._cluster_map.get(track.display_name)
        if cid is not None:
            return cid
        return self.predict_cluster(track)

    def cluster_genre(self, cluster_id: int) -> str:
        """Human-readable genre label for a cluster id."""
        return self.genre_labels.get(cluster_id, f"cluster_{cluster_id}")

    def genre_for(self, track: Track) -> str:
        """Return the genre label for ``track`` (cluster_map → predict → label)."""
        return self.cluster_genre(self.cluster_id_for(track))

    # ── inspection ────────────────────────────────────────────────────────────

    def genre_summary(self) -> dict[str, int]:
        """
        Return ``{genre_label: cluster_id}`` — useful for inspecting what
        labels were assigned to each of the k clusters.
        """
        return {label: cid for cid, label in self.genre_labels.items()}

    def __repr__(self) -> str:
        k = len(self.genre_labels)
        return f"<GenrePredictor k={k} genres={list(self.genre_labels.values())}>"
