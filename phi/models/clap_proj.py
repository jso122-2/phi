"""
CLAPProjection — bridges audio embeddings into OctopusTracer's H space.

Architecture (LOCKED — CLAPProjection and PhiGraph agent-log):

    CLAPProjection: single Linear(512, 256) + L2-normalised output.
    CLAP's 512-d audio vectors are geometrically aligned (contrastive
    language-audio training) — a linear rotation/scale is sufficient.

Two embedding sources (pre-computed .npy path wins; metadata fallback):

    1. Pre-computed CLAP  — load <track>.npy (512-d float32 vector)
                            → CLAPProjection(512→256) → L2-norm
    2. MetadataEncoder    — encode JSON metadata into 512-d feature vector
                            → CLAPProjection(512→256) → L2-norm
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import numpy as np

from phi.models._metadata_encoder import D_IN, TAG_VOCAB_SIZE, MetadataEncoder
from phi._track import Track

__all__ = ["CLAPProjection", "MetadataEncoder", "embed_tracks", "D_OUT", "D_IN", "TAG_VOCAB_SIZE"]

# Output dimension
D_OUT: int = 256
_DEFAULT_CKPT = Path.home() / ".phi" / "clap_proj.npz"


class CLAPProjection:
    """
    numpy Linear(512, 256) + L2-normalised output.

    Parameters
    ----------
    rng : optional numpy Generator — for weight initialisation
    """

    def __init__(self, rng: Optional[np.random.Generator] = None) -> None:
        rng = rng or np.random.default_rng(42)
        scale = math.sqrt(1.0 / D_IN)
        self.W: np.ndarray = (
            rng.standard_normal((D_OUT, D_IN)).astype(np.float64) * scale
        )
        self.b: np.ndarray = np.zeros(D_OUT, dtype=np.float64)

    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        Parameters
        ----------
        x : (N, 512) float — CLAP or metadata embeddings

        Returns
        -------
        h : (N, 256) float — L2-normalised projected embeddings

        Notes
        -----
        Zero-norm rows (e.g. tracks with no metadata) are replaced with a
        canonical fallback unit vector (normalised W[0]) rather than being
        left as zero vectors.  0⃗ / scalar = 0⃗ regardless of the scalar, so
        the old guard (replace norm with 1e-12) could not enforce the invariant.
        """
        x = np.asarray(x, dtype=np.float64)
        h = x @ self.W.T + self.b                                # (N, D_OUT)
        norms = np.linalg.norm(h, axis=1, keepdims=True)         # (N, 1)
        zero_mask = (norms < 1e-12).ravel()                      # (N,) bool
        norms = np.where(norms < 1e-12, 1.0, norms)
        h = h / norms
        if zero_mask.any():
            # W is (D_OUT, D_IN); W[:, 0] is a (D_OUT,) vector in output space
            w_col = self.W[:, 0]
            w_col_norm = np.linalg.norm(w_col)
            fallback = (
                w_col / w_col_norm
                if w_col_norm > 1e-12
                else np.eye(D_OUT, dtype=np.float64)[0]
            )
            h[zero_mask] = fallback
        return h

    def save(self, path: str | Path) -> None:
        """Persist W, b to an npz (same layout as load())."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, W=self.W, b=self.b)

    @classmethod
    def load(cls, path: str | Path) -> "CLAPProjection":
        """Load W, b from an npz written by save()."""
        data = np.load(path)
        inst = cls.__new__(cls)
        inst.W = np.asarray(data["W"], dtype=np.float64)
        inst.b = np.asarray(data["b"], dtype=np.float64)
        if inst.W.shape != (D_OUT, D_IN) or inst.b.shape != (D_OUT,):
            raise ValueError(
                f"CLAPProjection checkpoint shape mismatch: W={inst.W.shape} b={inst.b.shape}"
            )
        return inst

    @classmethod
    def load_default(cls, rng: Optional[np.random.Generator] = None) -> "CLAPProjection":
        """Load ~/.phi/clap_proj.npz when present; otherwise Xavier-init."""
        if _DEFAULT_CKPT.exists():
            return cls.load(_DEFAULT_CKPT)
        return cls(rng=rng)

    @property
    def d_model(self) -> int:
        """Output dimension (256) — used by OctopusTracer to match its d_model."""
        return D_OUT

    @property
    def d_clap(self) -> int:
        """Input dimension (512) — CLAP audio embedding size expected by embed()."""
        return D_IN

    @property
    def n_params(self) -> int:
        return D_OUT * D_IN + D_OUT

    def project_library(self, library) -> tuple[np.ndarray, list[str]]:
        """
        Project all CLAP-annotated tracks in *library* into H-space.

        Iterates library.playlist and collects tracks whose annotation has
        ``mood_vec`` (512-d list[float] written by CLAPModel).  Falls back to
        loading a pre-computed ``.npy`` file from ``meta["clap_npy"]`` when no
        mood_vec annotation exists yet.

        Tracks with neither source are silently skipped — the caller (PhiGraph)
        reports them via coverage_report() so CLAPModel can be run on them.

        Parameters
        ----------
        library : phi.core.library.Library

        Returns
        -------
        H     : (N, D_OUT) float64 ndarray — L2-normalised projected embeddings
        paths : list[str] of length N — track paths, index-aligned with H rows
        """
        raw_vecs: list[np.ndarray] = []
        paths:    list[str]        = []

        for path in library.playlist:
            ann  = library.get_annotation(path)
            meta = library.get_meta(path) or {}

            vec: np.ndarray | None = None

            # Prefer live CLAPModel annotation (most up-to-date)
            mood_vec = ann.get("mood_vec")
            if mood_vec is not None:
                v = np.asarray(mood_vec, dtype=np.float64).flatten()
                if v.shape[0] == D_IN:
                    vec = v

            # Fallback: pre-computed .npy on disk
            if vec is None:
                npy_path = meta.get("clap_npy")
                if npy_path:
                    try:
                        v = np.load(str(npy_path)).astype(np.float64).flatten()
                        if v.shape[0] == D_IN:
                            vec = v
                    except Exception:
                        pass

            if vec is not None:
                raw_vecs.append(vec)
                paths.append(path)

        if not raw_vecs:
            return np.empty((0, D_OUT), dtype=np.float64), []

        X = np.stack(raw_vecs, axis=0)   # (N, D_IN)
        H = self.forward(X)              # (N, D_OUT) — already L2-normalised
        return H, paths

    def __repr__(self) -> str:
        return f"<CLAPProjection {D_IN}→{D_OUT} n_params={self.n_params:,}>"


def embed_tracks(
    tracks: list[Track],
    proj: CLAPProjection,
    encoder: MetadataEncoder,
    annotations: dict[str, dict] | None = None,
) -> np.ndarray:
    """
    Build (N, 512) input matrix — CLAP .npy when available, metadata otherwise.

    Parameters
    ----------
    tracks      : Track objects from PhiLibrary.
    proj        : CLAPProjection for the 512→256 projection step.
    encoder     : MetadataEncoder; must have set_vocab called before use.
    annotations : optional {path: ann_dict} mapping.  When supplied, consensus
                  dims [273:284] of the metadata vector are filled from each
                  track's annotation dict (valence, energy, BPM, mood, buoyancy).
                  CLAP .npy tracks are unaffected — they bypass the encoder.

    Returns
    -------
    X : (N, 512) float64 — raw input for CLAPProjection.forward()
    """
    anns = annotations or {}
    vecs: list[np.ndarray] = []
    for track in tracks:
        if track.clap_npy is not None:
            try:
                v = np.load(str(track.clap_npy)).astype(np.float64).flatten()
                if v.shape[0] == D_IN:
                    vecs.append(v)
                    continue
            except Exception:
                pass
        vecs.append(encoder.encode_one(track, ann=anns.get(str(track.path))))
    return np.stack(vecs, axis=0)
