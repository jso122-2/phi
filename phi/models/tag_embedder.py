"""phi.models.tag_embedder — numpy mood/genre embedding from track metadata.

Two embeddings, no torch required:

    genre_vec  (GENRE_DIM,)  TF-IDF over (lfm_tags + mb_genres + genre string)
                              → compact SVD projection (numpy linalg)
    mood_vec   (MOOD_DIM,)   [valence, energy, *mood_label_onehot] unit vector
                              → always available from Spotify enrichment

Both replace string-match / Jaccard fallbacks in phi.core.ranker._scoring when
written into Library.annotations.  The _session_*_vec fields on RankContext are
the mean of recent tracks' vectors — giving continuous-space session geometry
instead of plurality labels.

Checkpoint: ~/.phi/tag_embedder.npz  (override: PHI_TAG_EMBEDDER)
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from phi.core.library import Library

_log = logging.getLogger("phi.tag_embedder")

# ── dimensionality constants ───────────────────────────────────────────────────
GENRE_DIM: int = 64
MAX_VOCAB: int = 500

MOOD_LABELS: tuple[str, ...] = (
    "calm", "chill", "focused", "energetic", "happy", "sad", "angry",
)
MOOD_DIM: int = 2 + len(MOOD_LABELS)  # valence + energy + 7 labels = 9

_DEFAULT_CKPT = Path.home() / ".phi" / "tag_embedder.npz"
_LOCK = threading.Lock()


def _ckpt_path() -> Path:
    override = os.environ.get("PHI_TAG_EMBEDDER")
    return Path(override) if override else _DEFAULT_CKPT


class TagEmbedder:
    """Numpy track embedder: genre (TF-IDF+SVD) and mood (valence/energy/label).

    Input shapes
    ------------
    fit(library)          — Library with playlist + annotations + meta_cache
    encode_genre(ann, meta) — annotation dict, metadata dict  →  list[float] len GENRE_DIM
    encode_mood(ann, meta)  — annotation dict, metadata dict  →  list[float] len MOOD_DIM
    """

    def __init__(self) -> None:
        self._vocab: dict[str, int] = {}
        self._idf: np.ndarray | None = None          # (n_vocab,)
        self._components: np.ndarray | None = None   # (n_comp, n_vocab)
        self._fitted: bool = False

    # ── feature extraction helpers ─────────────────────────────────────────────

    @staticmethod
    def _tags(ann: dict, meta: dict) -> list[str]:
        """Collect all genre/tag strings for one track."""
        out: list[str] = []
        for t in (ann.get("lfm_tags") or []):
            s = str(t).lower().strip()
            if s:
                out.append(s)
        for t in (ann.get("mb_genres") or []):
            s = str(t).lower().strip()
            if s:
                out.append(s)
        g = (meta.get("genre") or ann.get("genre") or "").lower().strip()
        if g:
            out.append(g)
        return out

    # ── fit ───────────────────────────────────────────────────────────────────

    def fit(self, library: "Library") -> "TagEmbedder":
        """Fit genre TF-IDF + SVD projection on all tracks in *library*.

        Requires at least 2 tracks with tags for the SVD to be meaningful.
        Returns *self* for chaining.
        """
        docs: list[list[str]] = []
        for path in library.playlist:
            ann = library.annotations.get(path) or {}
            meta = library.meta_cache.get(path) or {}
            docs.append(self._tags(ann, meta))

        # Build vocabulary: top MAX_VOCAB tags by document frequency
        df_count: dict[str, int] = {}
        for tags in docs:
            for t in set(tags):        # unique per doc for DF
                df_count[t] = df_count.get(t, 0) + 1

        if not df_count:
            _log.warning("TagEmbedder.fit: no tags found in library — genre_vec disabled")
            self._fitted = True
            return self

        sorted_vocab = sorted(df_count, key=lambda k: -df_count[k])[:MAX_VOCAB]
        self._vocab = {t: i for i, t in enumerate(sorted_vocab)}
        n_vocab = len(self._vocab)
        n_docs = len(docs)

        # Build TF matrix (raw counts)
        X = np.zeros((n_docs, n_vocab), dtype=np.float32)
        for i, tags in enumerate(docs):
            for t in tags:
                if t in self._vocab:
                    X[i, self._vocab[t]] += 1.0

        # IDF: log((1 + n_docs) / (1 + df)) + 1  — sklearn-style smooth IDF
        df_arr = (X > 0).sum(axis=0).astype(np.float32)          # (n_vocab,)
        self._idf = np.log((1.0 + n_docs) / (1.0 + df_arr)) + 1.0

        # TF-IDF + L2 normalise rows
        X = X * self._idf[None, :]
        norms = np.linalg.norm(X, axis=1, keepdims=True)
        norms = np.where(norms == 0.0, 1.0, norms)
        X = X / norms

        # Compact SVD — keep top GENRE_DIM components
        n_comp = min(GENRE_DIM, n_vocab, n_docs - 1)
        if n_comp < 1:
            _log.warning("TagEmbedder.fit: too few tracks/vocab for SVD (%d docs, %d vocab)", n_docs, n_vocab)
            self._fitted = True
            return self

        try:
            # scipy.sparse.linalg.svds is faster but requires sparse input;
            # for ≤500 vocab dense numpy SVD is fast enough.
            _, _, Vt = np.linalg.svd(X, full_matrices=False)
            self._components = Vt[:n_comp, :].astype(np.float32)  # (n_comp, n_vocab)
            _log.info("TagEmbedder.fit: vocab=%d  docs=%d  components=%d", n_vocab, n_docs, n_comp)
        except np.linalg.LinAlgError as exc:
            _log.warning("TagEmbedder.fit: SVD failed (%s) — genre_vec disabled", exc)

        self._fitted = True
        return self

    # ── encode ────────────────────────────────────────────────────────────────

    def encode_genre(self, ann: dict, meta: dict) -> list[float]:
        """Project one track's tags to a GENRE_DIM-d unit vector.

        Returns [] when the embedder has no SVD components or the track has
        no tags (causing _genre_affinity to fall back to Jaccard).
        """
        if self._components is None or self._idf is None or not self._vocab:
            return []
        tags = self._tags(ann, meta)
        if not tags:
            return []

        n_vocab = len(self._vocab)
        x = np.zeros(n_vocab, dtype=np.float32)
        for t in tags:
            if t in self._vocab:
                x[self._vocab[t]] += 1.0
        x = x * self._idf
        norm = np.linalg.norm(x)
        if norm == 0.0:
            return []
        x = x / norm

        proj = self._components @ x                   # (n_comp,)
        proj_norm = np.linalg.norm(proj)
        if proj_norm == 0.0:
            return []
        return (proj / proj_norm).tolist()

    def encode_mood(self, ann: dict, meta: dict) -> list[float]:
        """Encode [valence, energy, *mood_label_onehot] as a MOOD_DIM unit vector.

        Returns [] when all components are zero (no enrichment data at all),
        so _mood_affinity correctly falls back to its next heuristic layer.
        """
        v = np.zeros(MOOD_DIM, dtype=np.float32)

        # Audio features (indices 0, 1)
        valence = ann.get("spotify_valence")
        energy = ann.get("spotify_energy")
        if valence is not None:
            v[0] = float(valence)
        if energy is not None:
            v[1] = float(energy)

        # Mood label one-hot (indices 2–8)
        label = (
            ann.get("spotify_mood") or ann.get("mood") or meta.get("mood") or ""
        ).lower().strip()
        if label:
            for i, ml in enumerate(MOOD_LABELS):
                if ml in label or label in ml:
                    v[2 + i] = 1.0
                    break

        norm = float(np.linalg.norm(v))
        if norm == 0.0:
            return []
        return (v / norm).tolist()

    # ── annotate library ──────────────────────────────────────────────────────

    def annotate(
        self,
        library: "Library",
        *,
        genre_key: str = "genre_vec",
        mood_key: str = "mood_vec",
        overwrite: bool = False,
    ) -> tuple[int, int]:
        """Write *genre_key* and *mood_key* into library.annotations for each track.

        Existing values are preserved unless *overwrite* is True — so CLAP
        vectors written by a torch model are never replaced by the numpy fallback.

        Returns (genre_count, mood_count) — number of tracks that received
        non-empty vectors (including pre-existing ones).
        """
        genre_n = 0
        mood_n = 0
        for path in library.playlist:
            ann = library.annotations.setdefault(path, {})
            meta = library.meta_cache.get(path) or {}
            if overwrite or not ann.get(genre_key):
                gv = self.encode_genre(ann, meta)
                if gv:
                    ann[genre_key] = gv
            if ann.get(genre_key):
                genre_n += 1
            if overwrite or not ann.get(mood_key):
                mv = self.encode_mood(ann, meta)
                if mv:
                    ann[mood_key] = mv
            if ann.get(mood_key):
                mood_n += 1
        _log.info(
            "TagEmbedder.annotate: genre_vec=%d/%d  mood_vec=%d/%d",
            genre_n, len(library.playlist), mood_n, len(library.playlist),
        )
        return genre_n, mood_n

    # ── session aggregates ────────────────────────────────────────────────────

    def session_genre_vec(
        self,
        paths: list[str],
        library: "Library",
        *,
        genre_key: str = "genre_vec",
    ) -> list[float]:
        """Mean genre_vec over *paths*. Returns [] when none of them have vecs."""
        vecs = []
        for p in paths:
            ann = library.annotations.get(p) or {}
            gv = ann.get(genre_key)
            if gv and len(gv) > 0:
                vecs.append(np.asarray(gv, dtype=np.float32))
        if not vecs:
            return []
        mean = np.mean(vecs, axis=0)
        norm = float(np.linalg.norm(mean))
        if norm == 0.0:
            return []
        return (mean / norm).tolist()

    def session_mood_vec(
        self,
        paths: list[str],
        library: "Library",
        *,
        mood_key: str = "mood_vec",
    ) -> list[float]:
        """Mean mood_vec over *paths*. Returns [] when none of them have vecs."""
        vecs = []
        for p in paths:
            ann = library.annotations.get(p) or {}
            mv = ann.get(mood_key)
            if mv and len(mv) > 0:
                vecs.append(np.asarray(mv, dtype=np.float32))
        if not vecs:
            return []
        mean = np.mean(vecs, axis=0)
        norm = float(np.linalg.norm(mean))
        if norm == 0.0:
            return []
        return (mean / norm).tolist()

    # ── persistence ───────────────────────────────────────────────────────────

    def save(self, path: str | Path) -> None:
        """Save genre SVD + IDF to an .npz file. Vocab stored as unicode array."""
        if self._idf is None or self._components is None or not self._vocab:
            _log.warning("TagEmbedder.save: nothing to save (not fitted with tags)")
            return
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        # Store vocab as a sorted string array (index = column position)
        vocab_list = [""] * len(self._vocab)
        for term, idx in self._vocab.items():
            vocab_list[idx] = term
        vocab_arr = np.array(vocab_list, dtype="U128")

        np.savez(
            p,
            idf=self._idf,
            components=self._components,
            vocab=vocab_arr,
        )
        _log.info("TagEmbedder.save → %s", p)

    @classmethod
    def load(cls, path: str | Path) -> "TagEmbedder":
        """Load from an .npz written by save(). Raises FileNotFoundError if absent."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(p)
        data = np.load(p, allow_pickle=False)
        obj = cls()
        obj._idf = data["idf"].astype(np.float32)
        obj._components = data["components"].astype(np.float32)
        vocab_arr = data["vocab"]
        obj._vocab = {str(term): int(i) for i, term in enumerate(vocab_arr)}
        obj._fitted = True
        _log.info("TagEmbedder.load ← %s  (vocab=%d  components=%s)", p, len(obj._vocab), obj._components.shape)
        return obj

    @classmethod
    def load_default(cls) -> "TagEmbedder | None":
        """Load from the default checkpoint path, or return None if absent."""
        try:
            return cls.load(_ckpt_path())
        except FileNotFoundError:
            return None
        except Exception as exc:
            _log.warning("TagEmbedder.load_default failed: %s", exc)
            return None

    def save_default(self) -> None:
        """Save to the default checkpoint path (~/.phi/tag_embedder.npz)."""
        self.save(_ckpt_path())
