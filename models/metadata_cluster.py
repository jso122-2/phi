"""
models.metadata_cluster — unsupervised clustering of Spotify metadata.

Pipeline
--------
1.  PhiLibrary.scan()       → 372 Track objects
2.  MetadataEncoder.encode() → (N, 512) float64
3.  L2-normalise + PCA       → (N, n_components) via numpy SVD
4.  K-means                  → cluster labels  (scipy.cluster.vq)
5.  XGBoost classifier       → trained on cluster labels → feature importance
6.  Save artefacts to  models/cluster_out/

Usage
-----
    python -m models.metadata_cluster          # default k=8
    python -m models.metadata_cluster --k 12
    python -m models.metadata_cluster --k 8 --pca 32
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.cluster.vq import kmeans2, whiten
import xgboost as xgb

from phi.library import PhiLibrary
from phi.models._metadata_encoder import MetadataEncoder

OUT_DIR = Path(__file__).parent / "cluster_out"

# ── feature name map ──────────────────────────────────────────────────────────
_CHROMATIC = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

def _feature_names(vocab: list[str]) -> list[str]:
    names: list[str] = []
    names += [f"key_{k}" for k in _CHROMATIC]          # [0:12]
    names += ["key_confidence", "duration_s",           # [12:17]
              "lfm_playcount", "lfm_listeners", "explicit"]
    names += [f"tag_{t}" for t in vocab]                # [17:17+len(vocab)]
    pad = 512 - 17 - len(vocab)
    names += [f"pad_{i}" for i in range(pad)]
    return names


# ── PCA (numpy SVD) ───────────────────────────────────────────────────────────

def pca_fit(X: np.ndarray, n_components: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Centre + SVD PCA.

    Returns
    -------
    X_pca   : (N, n_components)
    mean_   : (D,)
    V_T     : (n_components, D)  — top eigenvectors (rows)
    """
    mean_ = X.mean(axis=0)
    Xc = X - mean_
    _, _, Vt = np.linalg.svd(Xc, full_matrices=False)
    V_T = Vt[:n_components]
    return Xc @ V_T.T, mean_, V_T


def pca_transform(X: np.ndarray, mean_: np.ndarray, V_T: np.ndarray) -> np.ndarray:
    return (X - mean_) @ V_T.T


# ── main pipeline ─────────────────────────────────────────────────────────────

def run(k: int = 8, n_components: int = 50) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. load library
    lib = PhiLibrary()
    n_tracks = lib.scan()
    tracks = lib.tracks
    print(f"[metadata_cluster] loaded {n_tracks} tracks")

    # 2. encode metadata → (N, 512)
    enc = MetadataEncoder()
    vocab = lib.tag_vocabulary(top_k=256)
    enc.set_vocab(vocab)
    X = enc.encode(tracks)                        # (N, 512)
    print(f"[metadata_cluster] encoded  X shape={X.shape}")

    feature_names = _feature_names(enc._tag_vocab)

    # 3. PCA → (N, n_components)
    n_components = min(n_components, X.shape[0] - 1, X.shape[1])
    X_pca, mean_, V_T = pca_fit(X, n_components)
    print(f"[metadata_cluster] PCA     X_pca shape={X_pca.shape}")

    # 4. K-means (whiten for vq, then run kmeans2)
    X_w = whiten(X_pca)
    centroids, labels = kmeans2(X_w, k, iter=30, minit="points", seed=42)
    counts = np.bincount(labels, minlength=k)
    print(f"[metadata_cluster] k-means  k={k}  cluster sizes: {counts.tolist()}")

    # 5. XGBoost — supervised on cluster labels (gives feature importance)
    clf = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        use_label_encoder=False,
        eval_metric="mlogloss",
        verbosity=0,
        random_state=42,
    )
    clf.fit(X, labels)
    importances = clf.feature_importances_        # (512,)
    top_idx = np.argsort(importances)[::-1][:20]
    top_features = [(feature_names[i], float(importances[i])) for i in top_idx]
    print("[metadata_cluster] top-20 features by XGB importance:")
    for feat, imp in top_features:
        print(f"  {imp:.4f}  {feat}")

    # 6. save artefacts
    np.save(OUT_DIR / "labels.npy", labels)
    np.save(OUT_DIR / "centroids.npy", centroids)
    np.save(OUT_DIR / "X_encoded.npy", X)
    np.save(OUT_DIR / "X_pca.npy", X_pca)
    np.save(OUT_DIR / "importances.npy", importances)
    clf.save_model(str(OUT_DIR / "xgb_cluster.json"))

    track_names = [t.display_name for t in tracks]
    cluster_map = {track_names[i]: int(labels[i]) for i in range(n_tracks)}
    with open(OUT_DIR / "cluster_map.json", "w", encoding="utf-8") as f:
        json.dump(cluster_map, f, ensure_ascii=False, indent=2)

    _save_importance_plot(feature_names, importances, top_n=20)

    result = {
        "n_tracks": n_tracks,
        "k": k,
        "n_components": n_components,
        "cluster_sizes": counts.tolist(),
        "top_features": top_features,
        "out_dir": str(OUT_DIR),
    }
    with open(OUT_DIR / "run_meta.json", "w") as f:
        json.dump(result, f, indent=2)

    print(f"[metadata_cluster] artefacts saved → {OUT_DIR}")
    return result


def _save_importance_plot(feature_names: list[str], importances: np.ndarray, top_n: int = 20) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    top_idx = np.argsort(importances)[::-1][:top_n]
    names = [feature_names[i] for i in top_idx]
    vals  = importances[top_idx]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(names[::-1], vals[::-1], color="#4a9eff")
    ax.set_xlabel("XGBoost feature importance (gain)")
    ax.set_title(f"Top {top_n} metadata features for cluster separation")
    ax.tick_params(labelsize=8)
    plt.tight_layout()
    fig.savefig(OUT_DIR / "importance.png", dpi=150)
    plt.close(fig)
    print(f"[metadata_cluster] plot saved → {OUT_DIR / 'importance.png'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=8, help="number of clusters")
    parser.add_argument("--pca", type=int, default=50, help="PCA components")
    args = parser.parse_args()
    run(k=args.k, n_components=args.pca)
