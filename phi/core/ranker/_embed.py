"""phi.core.ranker._embed — TagEmbedder singleton wired to the ranker.

Responsibilities
----------------
1. ``maybe_fit_and_annotate(library)``
   Called once at session restore (in a background thread).  Loads the
   saved TagEmbedder, or fits a fresh one if no checkpoint exists, then
   writes genre_vec / mood_vec to every track in Library.annotations.

2. ``session_vecs(paths, library)``
   Called inside RankContext.from_library.  Reads already-annotated vecs
   and returns the (genre_vec, mood_vec) mean of the recent-tracks window.
   This is O(n×d) — n=8, d≤64 — negligible per-rank call.

The embedder is a module-level singleton so fit() only runs once per
process even if multiple callers race.
"""
from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phi.core.library import Library

_log = logging.getLogger("phi.ranker.embed")
_lock = threading.Lock()
_embedder = None   # type: ignore[assignment]  # TagEmbedder | None
_ready = False


def _get_embedder():
    """Return the module-level TagEmbedder, or None if not yet ready."""
    return _embedder


def maybe_fit_and_annotate(library: "Library") -> bool:
    """Load or fit the TagEmbedder, then annotate the whole library.

    Idempotent — if the embedder is already loaded this call is a no-op
    (returns True immediately).  Safe to call from a background thread.

    Returns True on success, False on any error.
    """
    global _embedder, _ready

    with _lock:
        if _ready:
            return True

    try:
        from phi.models.tag_embedder import TagEmbedder

        # Try loading a saved checkpoint first
        emb = TagEmbedder.load_default()
        if emb is None:
            _log.info("TagEmbedder: no checkpoint — fitting from library (n=%d)", len(library.playlist))
            emb = TagEmbedder()
            emb.fit(library)
            if emb._fitted:
                try:
                    emb.save_default()
                except Exception as exc:
                    _log.warning("TagEmbedder: save_default failed: %s", exc)
        else:
            _log.info("TagEmbedder: loaded from checkpoint")

        genre_n, mood_n = emb.annotate(library)
        _log.info(
            "TagEmbedder: annotated  genre_vec=%d  mood_vec=%d  total=%d",
            genre_n, mood_n, len(library.playlist),
        )

        with _lock:
            _embedder = emb
            _ready = True
        return True

    except Exception as exc:
        _log.warning("maybe_fit_and_annotate failed: %s", exc)
        return False


def session_vecs(
    paths: list[str],
    library: "Library",
) -> tuple[list[float], list[float]]:
    """Return (session_genre_vec, session_mood_vec) for *paths*.

    Both are mean unit vectors of the tracks' stored genre_vec / mood_vec.
    Returns ([], []) when the embedder is not ready or the tracks have no vecs.
    """
    emb = _get_embedder()
    if emb is None or not paths:
        return [], []
    try:
        gv = emb.session_genre_vec(paths, library)
        mv = emb.session_mood_vec(paths, library)
        return gv, mv
    except Exception as exc:
        _log.debug("session_vecs error: %s", exc)
        return [], []


def refetch_embedder() -> None:
    """Force the singleton to reload on the next call (for tests / refit)."""
    global _embedder, _ready
    with _lock:
        _embedder = None
        _ready = False
