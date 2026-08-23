"""
phi.models.psp_index — Stage I P_sps pre-computation SQLite index.

Pre-computes TF-IDF vectors for all tracks and caches them in a SQLite
database with mtime-based invalidation.  H-space scores are NOT cached
because they depend on the current snap.H which changes when the library
is rescanned.

Schema
------
  tracks  : one row per track — path (PK), text, mtime, tfidf_vec (blob)
  vocab   : single row (id=1) — JSON-serialised list[str] of TF-IDF terms

Consistency contract
--------------------
When any track is dirty the full TF-IDF corpus is rebuilt (to keep IDF
weights correct).  If the resulting vocabulary differs from the stored one
every row is rewritten so tfidf_matrix() always returns a uniform (N, V)
array.  The return value of build() reflects only the number of rows whose
mtime changed, matching the "skip unchanged" contract.
"""
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from phi._track import Track
from phi.models.gemini_clipper import _track_text
from psspps.scorer import build_tfidf

__all__ = ["PspEntry", "PspIndex"]

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL_TRACKS = """
CREATE TABLE IF NOT EXISTS tracks (
    track_path  TEXT PRIMARY KEY,
    track_text  TEXT NOT NULL,
    mtime       REAL NOT NULL,
    tfidf_vec   BLOB NOT NULL
)
"""

_DDL_VOCAB = """
CREATE TABLE IF NOT EXISTS vocab (
    id    INTEGER PRIMARY KEY CHECK (id = 1),
    terms TEXT NOT NULL
)
"""


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------


@dataclass
class PspEntry:
    """One cached row in the index."""

    track_path: str
    track_text: str
    mtime: float
    tfidf_vec: np.ndarray


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_mtime(path: str) -> float:
    """Return os.path.getmtime, or 0.0 if the file doesn't exist."""
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


# ---------------------------------------------------------------------------
# PspIndex
# ---------------------------------------------------------------------------


class PspIndex:
    """
    SQLite-backed pre-computation cache for Stage I of the Gemini Clipper.

    Parameters
    ----------
    db_path : path to the SQLite file to create / open.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(_DDL_TRACKS)
        self._conn.execute(_DDL_VOCAB)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self, tracks: list[Track]) -> int:
        """
        (Re)build the index from *tracks*.

        Identifies dirty tracks (new or mtime-changed), then rebuilds the
        full TF-IDF corpus to produce consistent vocabulary and IDF weights.

        If the vocabulary changes (new terms appeared) every stored row is
        rewritten so tfidf_matrix() always returns a uniform matrix.

        Parameters
        ----------
        tracks : current library snapshot

        Returns
        -------
        Number of rows written (new or updated by mtime change).
        """
        if not tracks:
            return 0

        # ── 1. Identify dirty tracks ─────────────────────────────────
        cur = self._conn.execute("SELECT track_path, mtime FROM tracks")
        cached_mtimes: dict[str, float] = {r[0]: r[1] for r in cur.fetchall()}

        dirty_paths: set[str] = set()
        current_mtimes: dict[str, float] = {}
        for track in tracks:
            p = str(track.path)
            mt = _get_mtime(p)
            current_mtimes[p] = mt
            if cached_mtimes.get(p) != mt:
                dirty_paths.add(p)

        n_dirty = len(dirty_paths)
        if n_dirty == 0:
            return 0

        # ── 2. Rebuild TF-IDF over the full corpus ───────────────────
        all_paths = [str(t.path) for t in tracks]
        all_texts = [_track_text(t) for t in tracks]
        tfidf_matrix, vocab = build_tfidf(all_texts)
        path_to_idx = {p: i for i, p in enumerate(all_paths)}

        # ── 3. Decide if we need to rewrite all rows ──────────────────
        stored_vocab = self._fetch_vocab()
        vocab_changed = vocab != stored_vocab

        if vocab_changed:
            # Rewrite all rows so every vector has the new vocab_size
            for i, path_str in enumerate(all_paths):
                vec = tfidf_matrix[i].astype(np.float64)
                self._conn.execute(
                    "INSERT OR REPLACE INTO tracks"
                    " (track_path, track_text, mtime, tfidf_vec)"
                    " VALUES (?, ?, ?, ?)",
                    (
                        path_str,
                        all_texts[i],
                        current_mtimes[path_str],
                        vec.tobytes(),
                    ),
                )
        else:
            # Only write dirty rows
            for track in tracks:
                p = str(track.path)
                if p not in dirty_paths:
                    continue
                idx = path_to_idx[p]
                vec = tfidf_matrix[idx].astype(np.float64)
                self._conn.execute(
                    "INSERT OR REPLACE INTO tracks"
                    " (track_path, track_text, mtime, tfidf_vec)"
                    " VALUES (?, ?, ?, ?)",
                    (
                        p,
                        all_texts[idx],
                        current_mtimes[p],
                        vec.tobytes(),
                    ),
                )

        # ── 4. Persist vocab ──────────────────────────────────────────
        self._conn.execute("DELETE FROM vocab")
        self._conn.execute(
            "INSERT INTO vocab (id, terms) VALUES (1, ?)",
            (json.dumps(vocab),),
        )
        self._conn.commit()

        return n_dirty

    def vocabulary(self) -> list[str]:
        """Return the TF-IDF vocabulary stored in the index."""
        return self._fetch_vocab()

    def tfidf_matrix(self) -> np.ndarray:
        """
        Return (N_indexed, vocab_size) TF-IDF matrix for all indexed tracks.

        Rows are ordered by track_path (ascending).
        """
        vocab = self._fetch_vocab()
        vocab_size = len(vocab)

        rows = self._conn.execute(
            "SELECT tfidf_vec FROM tracks ORDER BY track_path"
        ).fetchall()

        if not rows:
            return np.zeros((0, vocab_size), dtype=np.float64)

        vecs = [np.frombuffer(r[0], dtype=np.float64) for r in rows]
        return np.vstack(vecs)

    def track_paths(self) -> list[str]:
        """
        Return track paths in the same row order as tfidf_matrix().
        """
        rows = self._conn.execute(
            "SELECT track_path FROM tracks ORDER BY track_path"
        ).fetchall()
        return [r[0] for r in rows]

    def close(self) -> None:
        """Close the underlying SQLite connection. Safe to call multiple times."""
        try:
            self._conn.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_vocab(self) -> list[str]:
        row = self._conn.execute(
            "SELECT terms FROM vocab WHERE id = 1"
        ).fetchone()
        if row is None:
            return []
        return json.loads(row[0])
