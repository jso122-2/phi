"""
graph.store — account-scoped SQLite vault-graph store.

SQL is the pinned roll; Obsidian .md files are the facade.

Architecture (vault-only phase)
--------------------------------
  nodes        — every vault note (all three layers)
  edges        — directed wikilinks + semantic links
  session_meta — extra columns for agent session nodes
  usage_events — append-only event log (used / accessed / amended)

Write path (session nodes)
--------------------------
  1. VaultStore.upsert_session(...)  → writes nodes + session_meta rows
  2. Caller materialises .md via graph.node.write_session_node (unchanged)
  3. VaultStore.record_event(...)    → appends to usage_events

Write path (station / ingest nodes)
-------------------------------------
  Station notes are still human-authored .md; SQL is a mirror updated by
  VaultStore.upsert_from_vault_node().  Callers pass a VaultNode parsed from
  disk — no SQL-primary rewrite yet for those layers.

Schema rules
------------
- node_id = vault-relative path without .md suffix (forward-slash).
  e.g. "HOME", "sessions/2026-08-23-085100-foo", "keep/some-note"
- rel_path = vault-relative path with .md extension.
- WAL journal mode, NORMAL synchronous — safe, fast, single-file.
- text is NOT stored in the DB; .md is the text store.  text_hash detects drift.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

from graph.node import VAULT_ROOT as _VAULT_ROOT

DB_PATH: Path = _VAULT_ROOT / ".vault.db"

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous  = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS nodes (
    node_id     TEXT    PRIMARY KEY,
    rel_path    TEXT    NOT NULL UNIQUE,
    stem        TEXT    NOT NULL,
    title       TEXT,
    layer       TEXT    NOT NULL,           -- stations | sessions | ingest
    hub         TEXT,                       -- HOME | MATH | CODE | COMMANDS | agent-context
    tags        TEXT    NOT NULL DEFAULT '[]',  -- JSON array
    wikilinks   TEXT    NOT NULL DEFAULT '[]',  -- JSON array (outgoing)
    text_hash   TEXT,
    created_at  TEXT    NOT NULL,
    modified_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nodes_layer  ON nodes (layer);
CREATE INDEX IF NOT EXISTS idx_nodes_hub    ON nodes (hub);
CREATE INDEX IF NOT EXISTS idx_nodes_stem   ON nodes (stem);

CREATE TABLE IF NOT EXISTS edges (
    src_id  TEXT    NOT NULL,
    dst_stem TEXT   NOT NULL,
    kind    TEXT    NOT NULL DEFAULT 'wikilink',
    PRIMARY KEY (src_id, dst_stem, kind),
    FOREIGN KEY (src_id) REFERENCES nodes(node_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges (dst_stem);

CREATE TABLE IF NOT EXISTS session_meta (
    node_id          TEXT    PRIMARY KEY,
    prompt           TEXT,
    thinking         TEXT,
    outcome          TEXT,
    hub              TEXT,
    discovered_links TEXT    NOT NULL DEFAULT '[]',  -- JSON array
    rag_confidence   REAL,
    FOREIGN KEY (node_id) REFERENCES nodes(node_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS usage_events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    rel_path TEXT    NOT NULL,
    event    TEXT    NOT NULL,          -- used | accessed | amended
    n        INTEGER NOT NULL DEFAULT 1,
    ts       TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_usage_path  ON usage_events (rel_path);
CREATE INDEX IF NOT EXISTS idx_usage_event ON usage_events (event);
"""

# ---------------------------------------------------------------------------
# VaultStore
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()


def _node_id(rel_path: str) -> str:
    """Canonical node_id: rel_path without .md, forward-slashed."""
    rid = rel_path.replace("\\", "/").lstrip("/")
    return rid[:-3] if rid.endswith(".md") else rid


class VaultStore:
    """
    Thread-safe SQLite-backed store for the vault graph.

    One instance should be created at server spawn and closed at shutdown.
    The same WAL pattern used by phi.meta.cache: thread-safe reads,
    serialised writes through a Lock.
    """

    def __init__(self, db_path: Path = DB_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(db_path), check_same_thread=False, timeout=15.0
        )
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------
    # Node upsert — generic (station or ingest notes from disk)
    # ------------------------------------------------------------------

    def upsert_from_vault_node(
        self,
        node: "VaultNode",  # graph.node.VaultNode
        layer: str,
        hub: str | None = None,
    ) -> None:
        """
        Mirror a VaultNode parsed from disk into the SQL store.
        Silently skips if text_hash matches (no change).
        """
        from graph.node import VAULT_ROOT

        rel = node.rel_path.replace("\\", "/")
        nid = _node_id(rel)
        h = _text_hash(node.text)

        with self._lock:
            row = self._conn.execute(
                "SELECT text_hash FROM nodes WHERE node_id = ?", (nid,)
            ).fetchone()

            if row and row["text_hash"] == h:
                return  # unchanged

            ts = _now()
            self._conn.execute(
                """
                INSERT INTO nodes (node_id, rel_path, stem, title, layer, hub,
                                   tags, wikilinks, text_hash, created_at, modified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    title       = excluded.title,
                    layer       = excluded.layer,
                    hub         = excluded.hub,
                    tags        = excluded.tags,
                    wikilinks   = excluded.wikilinks,
                    text_hash   = excluded.text_hash,
                    modified_at = excluded.modified_at
                """,
                (
                    nid,
                    rel,
                    node.stem,
                    node.title,
                    layer,
                    hub,
                    json.dumps(node.tags),
                    json.dumps(node.wikilinks),
                    h,
                    ts,
                    ts,
                ),
            )
            # Rebuild wikilink edges for this node
            self._conn.execute("DELETE FROM edges WHERE src_id = ?", (nid,))
            if node.wikilinks:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO edges (src_id, dst_stem, kind) VALUES (?, ?, 'wikilink')",
                    [(nid, wl.split("/")[-1]) for wl in node.wikilinks],
                )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Session upsert — SQL-primary
    # ------------------------------------------------------------------

    def upsert_session(
        self,
        *,
        rel_path: str,
        title: str,
        hub: str,
        tags: list[str],
        wikilinks: list[str],
        text: str,
        prompt: str,
        thinking: str,
        outcome: str,
        discovered_links: list[str],
        rag_confidence: float | None = None,
    ) -> str:
        """
        Write a session node into SQL.  Returns node_id.

        The .md file is written separately by graph.node.write_session_node;
        this call makes SQL the source-of-truth for sessions.
        """
        rel = rel_path.replace("\\", "/")
        nid = _node_id(rel)
        stem = Path(rel).stem
        h = _text_hash(text)
        ts = _now()

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO nodes (node_id, rel_path, stem, title, layer, hub,
                                   tags, wikilinks, text_hash, created_at, modified_at)
                VALUES (?, ?, ?, ?, 'sessions', ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    title       = excluded.title,
                    hub         = excluded.hub,
                    tags        = excluded.tags,
                    wikilinks   = excluded.wikilinks,
                    text_hash   = excluded.text_hash,
                    modified_at = excluded.modified_at
                """,
                (
                    nid, rel, stem, title, hub,
                    json.dumps(tags),
                    json.dumps(wikilinks),
                    h, ts, ts,
                ),
            )
            self._conn.execute(
                """
                INSERT INTO session_meta
                    (node_id, prompt, thinking, outcome, hub, discovered_links, rag_confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    prompt           = excluded.prompt,
                    thinking         = excluded.thinking,
                    outcome          = excluded.outcome,
                    hub              = excluded.hub,
                    discovered_links = excluded.discovered_links,
                    rag_confidence   = excluded.rag_confidence
                """,
                (
                    nid, prompt, thinking, outcome, hub,
                    json.dumps(discovered_links),
                    rag_confidence,
                ),
            )
            # Edges
            self._conn.execute("DELETE FROM edges WHERE src_id = ?", (nid,))
            if wikilinks:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO edges (src_id, dst_stem, kind) VALUES (?, ?, 'wikilink')",
                    [(nid, wl.split("/")[-1]) for wl in wikilinks],
                )
            self._conn.commit()

        return nid

    # ------------------------------------------------------------------
    # Usage events
    # ------------------------------------------------------------------

    def record_event(self, rel_path: str, event: str, n: int = 1) -> None:
        """Append one usage event row. event ∈ {'used', 'accessed', 'amended'}."""
        rel = rel_path.replace("\\", "/").lstrip("/")
        if not rel.endswith(".md"):
            rel = f"{rel}.md"
        with self._lock:
            self._conn.execute(
                "INSERT INTO usage_events (rel_path, event, n, ts) VALUES (?, ?, ?, ?)",
                (rel, event, n, _now()),
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        """Return node row as dict, or None."""
        row = self._conn.execute(
            "SELECT * FROM nodes WHERE node_id = ?", (node_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_session(self, node_id: str) -> dict[str, Any] | None:
        """Return merged node + session_meta row, or None."""
        row = self._conn.execute(
            """
            SELECT n.*, s.prompt, s.thinking, s.outcome,
                   s.discovered_links, s.rag_confidence
            FROM nodes n
            JOIN session_meta s USING (node_id)
            WHERE n.node_id = ?
            """,
            (node_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """Most recent session nodes, newest first."""
        rows = self._conn.execute(
            """
            SELECT n.node_id, n.stem, n.title, n.hub,
                   n.created_at, s.rag_confidence
            FROM nodes n
            JOIN session_meta s USING (node_id)
            ORDER BY n.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_nodes(
        self,
        layer: str | None = None,
        hub: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Query nodes by layer and/or hub."""
        clauses: list[str] = []
        params: list[Any] = []
        if layer:
            clauses.append("layer = ?")
            params.append(layer)
        if hub:
            clauses.append("hub = ?")
            params.append(hub)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._conn.execute(
            f"SELECT node_id, rel_path, stem, title, layer, hub, created_at "
            f"FROM nodes {where} ORDER BY modified_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def incoming_links(self, stem: str, limit: int = 50) -> list[str]:
        """node_ids that wikilink to *stem*."""
        rows = self._conn.execute(
            "SELECT src_id FROM edges WHERE dst_stem = ? LIMIT ?",
            (stem.split("/")[-1], limit),
        ).fetchall()
        return [r["src_id"] for r in rows]

    def usage_summary(self, rel_path: str) -> dict[str, int]:
        """Aggregate used/accessed/amended counts for a path from the event log."""
        rel = rel_path.replace("\\", "/").lstrip("/")
        if not rel.endswith(".md"):
            rel = f"{rel}.md"
        rows = self._conn.execute(
            "SELECT event, SUM(n) as total FROM usage_events WHERE rel_path = ? GROUP BY event",
            (rel,),
        ).fetchall()
        out: dict[str, int] = {"used": 0, "accessed": 0, "amended": 0}
        for r in rows:
            if r["event"] in out:
                out[r["event"]] = int(r["total"] or 0)
        return out

    def stats(self) -> dict[str, Any]:
        """Quick health snapshot."""
        n_nodes = self._conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        n_sessions = self._conn.execute(
            "SELECT COUNT(*) FROM session_meta"
        ).fetchone()[0]
        n_edges = self._conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        n_events = self._conn.execute("SELECT COUNT(*) FROM usage_events").fetchone()[0]
        by_layer = {
            r[0]: r[1]
            for r in self._conn.execute(
                "SELECT layer, COUNT(*) FROM nodes GROUP BY layer"
            ).fetchall()
        }
        return {
            "db_path": str(self._db_path),
            "n_nodes": n_nodes,
            "n_sessions": n_sessions,
            "n_edges": n_edges,
            "n_usage_events": n_events,
            "by_layer": by_layer,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def node_id_for(rel_path: str) -> str:
        """Public helper: convert a rel_path to its canonical node_id."""
        return _node_id(rel_path)


# ---------------------------------------------------------------------------
# Module-level singleton (lazy, for MCP server re-use)
# ---------------------------------------------------------------------------

_store: VaultStore | None = None
_store_lock = threading.Lock()


def get_store(db_path: Path = DB_PATH) -> VaultStore:
    """Return the module-level VaultStore singleton, creating it if needed."""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = VaultStore(db_path)
    return _store


def reset_store() -> None:
    """Close and discard the singleton (for tests)."""
    global _store
    with _store_lock:
        if _store is not None:
            try:
                _store.close()
            except Exception:
                pass
            _store = None
