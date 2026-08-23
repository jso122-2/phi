"""
HealthLog — SQLite append-only log for vault topology snapshots.

Records one row per coherence cycle with the key topological metrics.
Used by the daemon to track χ over time and by the canvas dashboard
to render trend data. Agents can also write directly via samba_record_coherence.

Schema:
    snapshots(ts, chi, notes, edges, triangles, orphan_count, wikilink_count,
              links_written, bridges_created, comment)

Public API:
    HealthLog(db_path)
    .append(snapshot: dict) -> None
    .recent(n=50) -> List[dict]
    .latest() -> Optional[dict]
"""
import logging
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).parent.parent / "logs" / "coherence_health.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS snapshots (
    ts              INTEGER PRIMARY KEY,
    chi             REAL,
    notes           INTEGER,
    edges           INTEGER,
    triangles       INTEGER,
    orphan_count    INTEGER,
    wikilink_count  INTEGER,
    links_written   INTEGER DEFAULT 0,
    bridges_created INTEGER DEFAULT 0,
    comment         TEXT
);
"""

# Safe migration: add comment column if the table already exists without it.
_MIGRATE_COMMENT = "ALTER TABLE snapshots ADD COLUMN comment TEXT;"

_INSERT = """
INSERT OR REPLACE INTO snapshots
    (ts, chi, notes, edges, triangles, orphan_count, wikilink_count,
     links_written, bridges_created, comment)
VALUES
    (:ts, :chi, :notes, :edges, :triangles, :orphan_count, :wikilink_count,
     :links_written, :bridges_created, :comment);
"""

_SELECT_RECENT = """
SELECT ts, chi, notes, edges, triangles, orphan_count, wikilink_count,
       links_written, bridges_created, comment
FROM snapshots
ORDER BY ts DESC
LIMIT ?;
"""

_SELECT_LATEST = """
SELECT ts, chi, notes, edges, triangles, orphan_count, wikilink_count,
       links_written, bridges_created, comment
FROM snapshots
ORDER BY ts DESC
LIMIT 1;
"""


class HealthLog:
    """
    Append-only SQLite log for coherence cycle snapshots.

    Args:
        db_path: Path to the SQLite file. Created automatically if absent.
                 Parent directory must exist.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def append(self, snapshot: Dict) -> None:
        """
        Write a topology snapshot.

        The snapshot dict may contain any subset of the schema columns.
        Missing fields default to 0 / None. `ts` defaults to current Unix time.
        `comment` is an optional free-text annotation (e.g. an agent's reasoning).

        Args:
            snapshot: dict with keys matching schema columns.
        """
        row = {
            "ts":              snapshot.get("ts", int(time.time())),
            "chi":             snapshot.get("chi"),
            "notes":           snapshot.get("notes"),
            "edges":           snapshot.get("edges"),
            "triangles":       snapshot.get("triangles"),
            "orphan_count":    snapshot.get("orphan_count", 0),
            "wikilink_count":  snapshot.get("wikilink_count"),
            "links_written":   snapshot.get("links_written", 0),
            "bridges_created": snapshot.get("bridges_created", 0),
            "comment":         snapshot.get("comment"),
        }
        with self._connect() as conn:
            conn.execute(_INSERT, row)
        logger.debug("HealthLog: appended snapshot ts=%d chi=%.1f", row["ts"], row["chi"] or 0)

    def recent(self, n: int = 50) -> List[Dict]:
        """
        Return the N most recent snapshots, newest first.

        Returns:
            List of dicts matching the schema columns.
        """
        with self._connect() as conn:
            rows = conn.execute(_SELECT_RECENT, (n,)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def latest(self) -> Optional[Dict]:
        """Return the single most recent snapshot, or None if the log is empty."""
        with self._connect() as conn:
            row = conn.execute(_SELECT_LATEST).fetchone()
        return self._row_to_dict(row) if row else None

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE)
            # Migrate existing DBs that predate the comment column.
            try:
                conn.execute(_MIGRATE_COMMENT)
            except Exception:
                pass  # column already exists — ignore OperationalError

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict:
        return dict(row)
