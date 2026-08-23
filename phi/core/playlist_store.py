# -*- coding: utf-8 -*-
"""phi.core.playlist_store — named playlist persistence (SQLite).

Schema (written into ~/.phi/meta.db alongside the metadata cache):

    playlists (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    UNIQUE NOT NULL,
        created_at  REAL    NOT NULL,
        updated_at  REAL    NOT NULL,
        spotify_id  TEXT    UNIQUE,          -- Spotify playlist ID, NULL for local playlists
        owner       TEXT,                    -- Spotify owner username
    )

    playlist_tracks (
        playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
        path        TEXT    NOT NULL,
        position    INTEGER NOT NULL,
        PRIMARY KEY (playlist_id, position),
    )

Thread safety: all writes go through a single threading.Lock.
Reads use a separate connection (WAL mode allows concurrent readers).

Spotify playlists imported via ``upsert_spotify_playlist()`` are tagged with
their original ``spotify_id`` and ``owner``.  Use ``by_spotify_id()`` to look
them up and ``all_spotify()`` to list only the Spotify-origin playlists.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import NamedTuple


class PlaylistInfo(NamedTuple):
    id:          int
    name:        str
    created_at:  float
    updated_at:  float
    track_count: int
    spotify_id:  str | None = None
    owner:       str | None = None


class SpotifyPlaylistInfo(NamedTuple):
    """Extended info for a Spotify-origin playlist."""
    id:           int
    name:         str
    created_at:   float
    updated_at:   float
    track_count:  int
    spotify_id:   str
    owner:        str


class PlaylistStore:
    """
    Manages named playlists in SQLite.

    One instance is shared across the application and lives for the full
    session.  Call close() on app shutdown.
    """

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    # ── schema ────────────────────────────────────────────────────────────────

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS playlists (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    UNIQUE NOT NULL,
                    created_at  REAL    NOT NULL,
                    updated_at  REAL    NOT NULL
                );
                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    playlist_id INTEGER NOT NULL
                                REFERENCES playlists(id) ON DELETE CASCADE,
                    path        TEXT    NOT NULL,
                    position    INTEGER NOT NULL,
                    PRIMARY KEY (playlist_id, position)
                );
                CREATE INDEX IF NOT EXISTS idx_pt_playlist
                    ON playlist_tracks(playlist_id);
            """)
            # Migrate before committing so new indexes see the new columns.
            self._migrate_schema()
            self._conn.commit()

    def _migrate_schema(self) -> None:
        """Add spotify_id / owner columns to existing DBs that predate them."""
        existing = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(playlists)").fetchall()
        }
        # SQLite disallows UNIQUE on ALTER TABLE ADD COLUMN — add plain, then index.
        for col in ("spotify_id", "owner"):
            if col not in existing:
                self._conn.execute(
                    f"ALTER TABLE playlists ADD COLUMN {col} TEXT"
                )

        # Unique index on spotify_id replaces the column-level UNIQUE constraint.
        self._conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_pl_spotify_id
            ON playlists(spotify_id)
            WHERE spotify_id IS NOT NULL
        """)

    # ── playlist CRUD ──────────────────────────────────────────────────────────

    def create(self, name: str) -> int:
        """Create a new empty playlist.  Returns its id.  Raises on duplicate name."""
        now = time.time()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO playlists (name, created_at, updated_at) VALUES (?, ?, ?)",
                (name.strip(), now, now),
            )
            self._conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def rename(self, playlist_id: int, new_name: str) -> bool:
        """Rename a playlist.  Returns False if the name is already taken."""
        try:
            with self._lock:
                self._conn.execute(
                    "UPDATE playlists SET name=?, updated_at=? WHERE id=?",
                    (new_name.strip(), time.time(), playlist_id),
                )
                self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def delete(self, playlist_id: int) -> None:
        """Delete a playlist and all its tracks (CASCADE)."""
        with self._lock:
            self._conn.execute("DELETE FROM playlists WHERE id=?", (playlist_id,))
            self._conn.commit()

    def all(self) -> list[PlaylistInfo]:
        """Return all playlists ordered by name, including track counts."""
        rows = self._conn.execute("""
            SELECT p.id, p.name, p.created_at, p.updated_at,
                   COUNT(pt.path) AS track_count,
                   p.spotify_id, p.owner
            FROM   playlists p
            LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.id
            GROUP BY p.id
            ORDER BY p.name COLLATE NOCASE
        """).fetchall()
        return [PlaylistInfo(*r) for r in rows]

    def get(self, playlist_id: int) -> PlaylistInfo | None:
        row = self._conn.execute("""
            SELECT p.id, p.name, p.created_at, p.updated_at,
                   COUNT(pt.path) AS track_count,
                   p.spotify_id, p.owner
            FROM   playlists p
            LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.id
            WHERE  p.id = ?
            GROUP BY p.id
        """, (playlist_id,)).fetchone()
        return PlaylistInfo(*row) if row else None

    def by_spotify_id(self, spotify_id: str) -> PlaylistInfo | None:
        """Look up a playlist by its original Spotify playlist ID."""
        row = self._conn.execute("""
            SELECT p.id, p.name, p.created_at, p.updated_at,
                   COUNT(pt.path) AS track_count,
                   p.spotify_id, p.owner
            FROM   playlists p
            LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.id
            WHERE  p.spotify_id = ?
            GROUP BY p.id
        """, (spotify_id,)).fetchone()
        return PlaylistInfo(*row) if row else None

    def all_spotify(self) -> list[SpotifyPlaylistInfo]:
        """Return only Spotify-origin playlists ordered by name."""
        rows = self._conn.execute("""
            SELECT p.id, p.name, p.created_at, p.updated_at,
                   COUNT(pt.path) AS track_count,
                   p.spotify_id, p.owner
            FROM   playlists p
            LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.id
            WHERE  p.spotify_id IS NOT NULL
            GROUP BY p.id
            ORDER BY p.name COLLATE NOCASE
        """).fetchall()
        return [SpotifyPlaylistInfo(*r) for r in rows]

    # ── track management ──────────────────────────────────────────────────────

    def tracks(self, playlist_id: int) -> list[str]:
        """Return the ordered list of absolute paths for a playlist."""
        rows = self._conn.execute(
            "SELECT path FROM playlist_tracks WHERE playlist_id=? ORDER BY position",
            (playlist_id,),
        ).fetchall()
        return [r[0] for r in rows]

    def add_track(self, playlist_id: int, path: str) -> None:
        """Append a track to the end of the playlist (no-op if already present)."""
        with self._lock:
            existing = self._conn.execute(
                "SELECT 1 FROM playlist_tracks WHERE playlist_id=? AND path=?",
                (playlist_id, path),
            ).fetchone()
            if existing:
                return
            max_pos = self._conn.execute(
                "SELECT COALESCE(MAX(position), -1) FROM playlist_tracks WHERE playlist_id=?",
                (playlist_id,),
            ).fetchone()[0]
            self._conn.execute(
                "INSERT INTO playlist_tracks (playlist_id, path, position) VALUES (?,?,?)",
                (playlist_id, path, max_pos + 1),
            )
            self._conn.execute(
                "UPDATE playlists SET updated_at=? WHERE id=?",
                (time.time(), playlist_id),
            )
            self._conn.commit()

    def add_tracks(self, playlist_id: int, paths: list[str]) -> None:
        """Append multiple tracks (skipping duplicates)."""
        with self._lock:
            existing = {
                r[0] for r in self._conn.execute(
                    "SELECT path FROM playlist_tracks WHERE playlist_id=?",
                    (playlist_id,),
                ).fetchall()
            }
            max_pos = self._conn.execute(
                "SELECT COALESCE(MAX(position), -1) FROM playlist_tracks WHERE playlist_id=?",
                (playlist_id,),
            ).fetchone()[0]
            new = [p for p in paths if p not in existing]
            self._conn.executemany(
                "INSERT INTO playlist_tracks (playlist_id, path, position) VALUES (?,?,?)",
                [(playlist_id, p, max_pos + 1 + i) for i, p in enumerate(new)],
            )
            if new:
                self._conn.execute(
                    "UPDATE playlists SET updated_at=? WHERE id=?",
                    (time.time(), playlist_id),
                )
            self._conn.commit()

    def remove_track(self, playlist_id: int, path: str) -> None:
        """Remove a track and compact positions."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM playlist_tracks WHERE playlist_id=? AND path=?",
                (playlist_id, path),
            )
            # Recompact positions
            rows = self._conn.execute(
                "SELECT path FROM playlist_tracks WHERE playlist_id=? ORDER BY position",
                (playlist_id,),
            ).fetchall()
            self._conn.execute(
                "DELETE FROM playlist_tracks WHERE playlist_id=?", (playlist_id,)
            )
            self._conn.executemany(
                "INSERT INTO playlist_tracks (playlist_id, path, position) VALUES (?,?,?)",
                [(playlist_id, r[0], i) for i, r in enumerate(rows)],
            )
            self._conn.execute(
                "UPDATE playlists SET updated_at=? WHERE id=?",
                (time.time(), playlist_id),
            )
            self._conn.commit()

    def create_from_paths(self, name: str, paths: list[str]) -> int:
        """Create a new playlist pre-populated with *paths*.  Returns playlist id."""
        pid = self.create(name)
        self.add_tracks(pid, paths)
        return pid

    # ── Spotify-origin playlists ───────────────────────────────────────────────

    def upsert_spotify_playlist(
        self,
        spotify_id: str,
        name: str,
        owner: str,
        paths: list[str],
    ) -> tuple[int, bool]:
        """
        Create or refresh a Spotify-origin playlist.

        If a playlist with *spotify_id* already exists its name, owner, and
        track list are updated to match the supplied values — tracks that are
        no longer present are removed and new ones are appended in order.

        Parameters
        ----------
        spotify_id : Spotify playlist ID (the folder name on disk).
        name       : Human-readable playlist name from library.json.
        owner      : Spotify username of the playlist owner.
        paths      : Absolute audio-file paths in playlist order.

        Returns
        -------
        (playlist_id, created)  where *created* is True when a new row was
        inserted and False when an existing playlist was refreshed.
        """
        now = time.time()
        existing = self.by_spotify_id(spotify_id)

        with self._lock:
            if existing is None:
                cur = self._conn.execute(
                    "INSERT INTO playlists (name, created_at, updated_at, spotify_id, owner)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (name.strip(), now, now, spotify_id, owner),
                )
                self._conn.commit()
                pid = cur.lastrowid
                created = True
            else:
                pid = existing.id
                self._conn.execute(
                    "UPDATE playlists SET name=?, updated_at=?, owner=? WHERE id=?",
                    (name.strip(), now, owner, pid),
                )
                created = False

            # Rebuild track list to match supplied paths exactly (preserving order).
            self._conn.execute(
                "DELETE FROM playlist_tracks WHERE playlist_id=?", (pid,)
            )
            self._conn.executemany(
                "INSERT INTO playlist_tracks (playlist_id, path, position) VALUES (?,?,?)",
                [(pid, p, i) for i, p in enumerate(paths)],
            )
            self._conn.execute(
                "UPDATE playlists SET updated_at=? WHERE id=?", (now, pid)
            )
            self._conn.commit()

        return pid, created  # type: ignore[return-value]

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        with self._lock:
            self._conn.close()
