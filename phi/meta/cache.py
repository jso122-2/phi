# -*- coding: utf-8 -*-
"""phi.meta.cache — persistent SQLite metadata cache.

Stores per-file tag data keyed by absolute path.  A cached row is considered
fresh if the file's mtime on disk matches the mtime stored at scan time.
Stale rows (mtime changed → tags may have been edited) are automatically
evicted and re-read.

Schema
------
    tracks (
        path       TEXT PRIMARY KEY,
        mtime      REAL NOT NULL,          -- os.path.getmtime() at scan time
        title      TEXT,
        artist     TEXT,
        album      TEXT,
        album_artist TEXT,
        track_num  INTEGER,
        disc_num   INTEGER,
        year       TEXT,
        genre      TEXT,
        duration   REAL,
        bpm        REAL,
        key_sig    TEXT,
        comment    TEXT,
        art_bytes  BLOB,                   -- embedded album art (may be NULL)
        scanned_at TEXT NOT NULL           -- ISO-8601 timestamp
    )

Usage
-----
    cache = MetaCache(META_DB)            # call once, share across threads
    meta  = cache.get("/path/to/track.mp3")  # None → cache miss
    if meta is None:
        meta = read_meta("/path/to/track.mp3")
        cache.put("/path/to/track.mp3", meta)

    cache.close()                          # call on app shutdown
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    path         TEXT PRIMARY KEY,
    mtime        REAL    NOT NULL,
    title        TEXT,
    artist       TEXT,
    album        TEXT,
    album_artist TEXT,
    track_num    INTEGER,
    disc_num     INTEGER,
    year         TEXT,
    genre        TEXT,
    duration     REAL,
    bpm          REAL,
    key_sig      TEXT,
    comment      TEXT,
    art_bytes    BLOB,
    scanned_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artist ON tracks(artist);
CREATE INDEX IF NOT EXISTS idx_album  ON tracks(album);

CREATE TABLE IF NOT EXISTS annotations (
    path        TEXT PRIMARY KEY,
    data        TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_annotations_clipper_x
    ON annotations (json_extract(data, '$.clipper_x'))
    WHERE json_extract(data, '$.clipper_x') IS NOT NULL;
"""

_MTIME_TOLERANCE = 2.0   # seconds — FAT32 has 2 s mtime resolution


def _now() -> str:
    return datetime.now().isoformat()


def _json_default(obj: Any) -> Any:
    """JSON encoder fallback — handles numpy arrays and similar types."""
    try:
        import numpy as np
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
    except ImportError:
        pass
    raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")


class MetaCache:
    """
    Thread-safe SQLite metadata cache.

    One instance should be created at app startup and closed at shutdown.
    The underlying SQLite connection uses WAL journal mode which allows
    concurrent reads from multiple threads without blocking.

    All writes are serialised through a Lock to prevent corruption.
    """

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock   = threading.Lock()
        self._closed = False   # set True by close(); all readers check this first
        # timeout=15: wait up to 15 s when another writer holds the WAL lock
        # rather than immediately raising OperationalError: database is locked.
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=15.0)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")   # safe with WAL
        self._conn.execute("PRAGMA cache_size=-32768")    # 32 MB page cache
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    # ── schema ─────────────────────────────────────────────────────────────────

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # ── public read API ────────────────────────────────────────────────────────

    def get(self, path: str) -> dict | None:
        """
        Return the cached meta dict for *path*, or None on cache miss.

        A cache miss occurs when:
          - No row exists for *path*, or
          - The file's current mtime differs from the stored mtime (file was
            modified externally — tags may have changed).

        The returned dict has the same keys as ``phi.meta.reader.read_meta``:
        title, artist, album, track, year, art_bytes, duration — plus extras:
        album_artist, disc_num, genre, bpm, key, comment.
        """
        if self._closed:
            return None
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return None

        row = self._conn.execute(
            "SELECT * FROM tracks WHERE path = ?", (path,)
        ).fetchone()

        if row is None:
            return None

        if abs(row["mtime"] - mtime) > _MTIME_TOLERANCE:
            # File was modified — evict and signal miss
            self._evict(path)
            return None

        return _row_to_meta(row)

    def get_many(self, paths: list[str]) -> dict[str, dict]:
        """
        Bulk fetch: returns {path: meta} for all cache-fresh paths.
        Stale rows are silently omitted.
        """
        if not paths or self._closed:
            return {}
        placeholders = ",".join("?" * len(paths))
        rows = self._conn.execute(
            f"SELECT * FROM tracks WHERE path IN ({placeholders})", paths
        ).fetchall()

        result: dict[str, dict] = {}
        mtimes: dict[str, float] = {}
        for p in paths:
            try:
                mtimes[p] = os.path.getmtime(p)
            except OSError:
                pass

        stale: list[str] = []
        for row in rows:
            p = row["path"]
            if p not in mtimes:
                continue
            if abs(row["mtime"] - mtimes[p]) > _MTIME_TOLERANCE:
                stale.append(p)
            else:
                result[p] = _row_to_meta(row)

        if stale:
            with self._lock:
                self._conn.executemany(
                    "DELETE FROM tracks WHERE path = ?", [(p,) for p in stale]
                )
                self._conn.commit()

        return result

    # ── public write API ───────────────────────────────────────────────────────

    def put(self, path: str, meta: dict) -> None:
        """
        Store *meta* for *path*.  Overwrites any existing row.
        Called after a successful mutagen read.
        """
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return

        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO tracks
                    (path, mtime, title, artist, album, album_artist,
                     track_num, disc_num, year, genre, duration,
                     bpm, key_sig, comment, art_bytes, scanned_at)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    path,
                    mtime,
                    meta.get("title"),
                    meta.get("artist"),
                    meta.get("album"),
                    meta.get("album_artist"),
                    meta.get("track"),
                    meta.get("disc_num"),
                    meta.get("year"),
                    meta.get("genre"),
                    meta.get("duration"),
                    meta.get("bpm"),
                    meta.get("key") or meta.get("key_sig"),
                    meta.get("comment"),
                    meta.get("art_bytes"),   # may be None or bytes
                    _now(),
                ),
            )
            self._conn.commit()

    def patch_art(self, path: str, art_bytes: bytes) -> bool:
        """
        Write *art_bytes* into an existing cache row without touching any
        other field or the mtime.  Used by the art spider so a targeted
        UPDATE never invalidates the rest of the metadata.

        Returns True if a row existed and was updated, False if not found.
        """
        with self._lock:
            cur = self._conn.execute(
                "UPDATE tracks SET art_bytes = ? WHERE path = ?",
                (art_bytes, path),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def paths_missing_art(self) -> list[str]:
        """
        Return all cached paths whose art_bytes column is NULL.
        Used by the art spider to find work to do.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT path FROM tracks WHERE art_bytes IS NULL ORDER BY ROWID"
            ).fetchall()
        return [r["path"] for r in rows]

    def iter_art_bytes(self):
        """
        Yield ``(path, art_bytes)`` for every row that has art.

        Used by the batch ASCII bake.  Results are streamed with a server-side
        cursor so the full BLOB set is never held in memory at once.
        """
        if self._closed:
            return
        cur = self._conn.execute(
            "SELECT path, art_bytes FROM tracks WHERE art_bytes IS NOT NULL"
        )
        while True:
            row = cur.fetchone()
            if row is None:
                break
            yield row["path"], row["art_bytes"]

    def invalidate(self, path: str) -> None:
        """Force the next read of *path* to re-scan from file."""
        with self._lock:
            self._conn.execute("DELETE FROM tracks WHERE path = ?", (path,))
            self._conn.commit()

    def prune(self, known_paths: set[str]) -> int:
        """
        Remove rows for paths no longer in the library.
        Returns the number of rows deleted.
        """
        with self._lock:
            rows = self._conn.execute("SELECT path FROM tracks").fetchall()
            orphans = [r["path"] for r in rows if r["path"] not in known_paths]
            if orphans:
                self._conn.executemany(
                    "DELETE FROM tracks WHERE path = ?", [(p,) for p in orphans]
                )
                self._conn.commit()
        return len(orphans if orphans else [])

    # ── stats / maintenance ────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return a summary dict suitable for display."""
        if self._closed:
            return {}
        row = self._conn.execute(
            "SELECT COUNT(*) AS n, "
            "       SUM(CASE WHEN art_bytes IS NOT NULL THEN 1 ELSE 0 END) AS with_art, "
            "       SUM(CASE WHEN artist IS NULL THEN 1 ELSE 0 END)        AS no_artist, "
            "       SUM(CASE WHEN title  IS NULL THEN 1 ELSE 0 END)        AS no_title "
            "FROM tracks"
        ).fetchone()
        db_size = Path(self._conn.execute(
            "PRAGMA database_list"
        ).fetchone()[2]).stat().st_size if True else 0
        try:
            import sqlite3 as _s3
            db_file = self._conn.execute("PRAGMA database_list").fetchone()[2]
            db_size = os.path.getsize(db_file) if db_file else 0
        except Exception:
            db_size = 0

        return {
            "cached_tracks": row["n"],
            "with_art":      row["with_art"],
            "no_artist":     row["no_artist"],
            "no_title":      row["no_title"],
            "db_bytes":      db_size,
        }

    # ── annotation API ────────────────────────────────────────────────────────

    def get_annotation(self, path: str) -> dict | None:
        """Return the persisted annotation dict for *path*, or None."""
        if self._closed:
            return None
        row = self._conn.execute(
            "SELECT data FROM annotations WHERE path = ?", (path,)
        ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row["data"])
        except Exception:
            return None

    def put_annotation(self, path: str, ann: dict) -> None:
        """Persist *ann* for *path*.  Overwrites any existing row."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO annotations (path, data, updated_at) "
                "VALUES (?, ?, ?)",
                (path, json.dumps(ann, default=_json_default), _now()),
            )
            self._conn.commit()

    def get_anchored_annotations(self, field: str = "clipper_x") -> dict[str, dict]:
        """
        Return {path: annotation_dict} for every row that contains *field*
        as a top-level JSON key.

        Uses SQLite json_extract (3.9+) so it never scans irrelevant blobs
        and requires no path list.  Ideal for scatter-plot loading.
        """
        if self._closed:
            return {}
        try:
            rows = self._conn.execute(
                f"SELECT path, data FROM annotations"
                f" WHERE json_extract(data, '$.{field}') IS NOT NULL",
            ).fetchall()
        except Exception:
            return {}
        result: dict[str, dict] = {}
        for row in rows:
            try:
                result[row["path"]] = json.loads(row["data"])
            except Exception:
                pass
        return result

    def get_many_annotations(self, paths: list[str]) -> dict[str, dict]:
        """Bulk fetch: returns {path: annotation_dict} for all stored paths."""
        if not paths or self._closed:
            return {}
        placeholders = ",".join("?" * len(paths))
        rows = self._conn.execute(
            f"SELECT path, data FROM annotations WHERE path IN ({placeholders})",
            paths,
        ).fetchall()
        result: dict[str, dict] = {}
        for row in rows:
            try:
                result[row["path"]] = json.loads(row["data"])
            except Exception:
                pass
        return result

    def put_many_annotations(self, annotations: dict[str, dict]) -> None:
        """Bulk upsert all entries in *annotations*.  Skips empty dicts."""
        if not annotations:
            return
        now = _now()
        rows = [
            (path, json.dumps(ann, default=_json_default), now)
            for path, ann in annotations.items()
            if ann
        ]
        if not rows:
            return
        with self._lock:
            self._conn.executemany(
                "INSERT OR REPLACE INTO annotations (path, data, updated_at) "
                "VALUES (?, ?, ?)",
                rows,
            )
            self._conn.commit()

    def drop_annotation(self, path: str) -> None:
        """Remove the stored annotation for *path* (e.g. after file delete)."""
        with self._lock:
            self._conn.execute("DELETE FROM annotations WHERE path = ?", (path,))
            self._conn.commit()

    def prune_annotations(self, known_paths: set[str]) -> int:
        """Remove annotation rows for paths no longer in the library."""
        with self._lock:
            rows = self._conn.execute("SELECT path FROM annotations").fetchall()
            orphans = [r["path"] for r in rows if r["path"] not in known_paths]
            if orphans:
                self._conn.executemany(
                    "DELETE FROM annotations WHERE path = ?",
                    [(p,) for p in orphans],
                )
                self._conn.commit()
        return len(orphans)

    # ── close ──────────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the SQLite connection.  Call on application shutdown."""
        with self._lock:
            self._closed = True   # signal all reader threads before closing
        try:
            self._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            self._conn.close()
        except Exception:
            pass

    # ── internal ───────────────────────────────────────────────────────────────

    def _evict(self, path: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM tracks WHERE path = ?", (path,))
            self._conn.commit()


# ── row → dict ────────────────────────────────────────────────────────────────

def _row_to_meta(row: sqlite3.Row) -> dict:
    """Convert a SQLite row to the same dict shape as read_meta()."""
    return {
        "title":        row["title"],
        "artist":       row["artist"],
        "album":        row["album"],
        "album_artist": row["album_artist"],
        "track":        row["track_num"],
        "disc_num":     row["disc_num"],
        "year":         row["year"],
        "genre":        row["genre"],
        "duration":     row["duration"],
        "bpm":          row["bpm"],
        "key":          row["key_sig"],
        "comment":      row["comment"],
        "art_bytes":    row["art_bytes"],   # bytes or None
    }

# Related: TagEditorDialog
