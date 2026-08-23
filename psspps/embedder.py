"""
MiniLM embedder — ONNX runtime, zero torch dependency.

Model:  sentence-transformers/all-MiniLM-L6-v2
        22 M params, 384-dim output, cosine-similarity friendly.

Weight cache:  <vault>/.cache/minilm/          (fastembed-managed, git-ignored)
Embedding cache: <vault>/.cache/embeddings.npz  (keyed by doc-content hash)

On first call the model is downloaded once (~23 MB) and stored in the vault
cache directory.  Subsequent calls hit disk only.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Sequence

import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_VAULT_ROOT = Path(__file__).parent.parent
_CACHE_DIR = _VAULT_ROOT / ".cache"
_MODEL_CACHE = _CACHE_DIR / "minilm"
_EMB_CACHE = _CACHE_DIR / "embeddings.npz"
_META_CACHE = _CACHE_DIR / "embeddings_meta.json"

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"  # fastembed resolves to qdrant/all-MiniLM-L6-v2-onnx

# ---------------------------------------------------------------------------
# Model singleton — lazy import so the package loads without fastembed present
# ---------------------------------------------------------------------------

_model = None


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding  # type: ignore[import]

        _MODEL_CACHE.mkdir(parents=True, exist_ok=True)
        _model = TextEmbedding(
            model_name=_MODEL_NAME,
            cache_dir=str(_MODEL_CACHE),
        )
    return _model


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def embed(texts: Sequence[str]) -> np.ndarray:
    """
    Embed a sequence of strings → float32 array of shape (N, 384).

    Each vector is L2-normalised (cosine similarity = dot product).
    """
    model = _get_model()
    vecs = list(model.embed(list(texts)))
    return np.stack(vecs).astype(np.float32)


def embed_docs(
    docs: list[dict],
    *,
    text_key: str = "clean_text",
    force: bool = False,
) -> np.ndarray:
    """
    Embed a list of VaultDoc dicts, using the on-disk cache when valid.

    Cache validity is determined by a SHA-256 of all doc texts concatenated.
    If any doc changes the cache is invalidated and rebuilt.

    Returns float32 array of shape (N, 384).
    """
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    texts = [d[text_key] for d in docs]
    cache_key = _content_hash(texts)

    if not force and _EMB_CACHE.exists() and _META_CACHE.exists():
        meta = json.loads(_META_CACHE.read_text())
        if meta.get("hash") == cache_key and meta.get("n") == len(texts):
            data = np.load(_EMB_CACHE)
            return data["embeddings"].astype(np.float32)

    embeddings = embed(texts)

    np.savez_compressed(_EMB_CACHE, embeddings=embeddings)
    _META_CACHE.write_text(
        json.dumps({"hash": cache_key, "n": len(texts), "model": _MODEL_NAME})
    )
    return embeddings


def cosine_matrix(query: np.ndarray, corpus: np.ndarray) -> np.ndarray:
    """
    Compute cosine similarities between a single query vector and a corpus.

    query  : (D,)
    corpus : (N, D) — assumes rows are L2-normalised (fastembed guarantees this)
    returns: (N,) similarities in [-1, 1]

    Uses float64 internally to avoid float32 overflow on matmul.
    """
    q = query.astype(np.float64)
    c = corpus.astype(np.float64)
    q = q / (np.linalg.norm(q) + 1e-12)
    norms = np.linalg.norm(c, axis=1, keepdims=True) + 1e-12
    normed = c / norms
    sims = normed @ q
    # Replace any residual NaN (zero-norm rows) with -2 so they're never chosen
    sims = np.where(np.isfinite(sims), sims, -2.0)
    return sims.astype(np.float32)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _content_hash(texts: list[str]) -> str:
    h = hashlib.sha256()
    for t in texts:
        h.update(t.encode("utf-8"))
    return h.hexdigest()
