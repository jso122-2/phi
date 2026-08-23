# -*- coding: utf-8 -*-
"""phi.models._derivative_loaders — raw I/O for the SongDerivativeModel.

Reads state.json, meta.db, and meta_store.jsonl from ~/.phi.
No feature engineering here — just dict-level data returned to callers.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

_PHI_DIR = Path.home() / ".phi"
_STATE   = _PHI_DIR / "state.json"
_META_DB = _PHI_DIR / "meta.db"
_STORE   = _PHI_DIR / "meta_store.jsonl"


def _load_state() -> dict:
    if not _STATE.exists():
        return {}
    try:
        return json.loads(_STATE.read_text())
    except Exception:
        return {}


def _load_annotations() -> dict[str, dict]:
    result: dict[str, dict] = {}
    if not _META_DB.exists():
        return result
    try:
        conn = sqlite3.connect(str(_META_DB))
        for path, data in conn.execute("SELECT path, data FROM annotations").fetchall():
            try:
                result[path] = json.loads(data)
            except Exception:
                pass
        conn.close()
    except Exception:
        pass
    return result


def _load_store() -> dict[str, dict]:
    result: dict[str, dict] = {}
    if not _STORE.exists():
        return result
    try:
        with _STORE.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        rec = json.loads(line)
                        if "path" in rec:
                            result[rec["path"]] = rec
                    except Exception:
                        pass
    except Exception:
        pass
    return result


def _load_tags() -> dict[str, dict]:
    """Load per-track metadata from the tracks table."""
    result: dict[str, dict] = {}
    if not _META_DB.exists():
        return result
    try:
        conn = sqlite3.connect(str(_META_DB))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT path, year, bpm, duration, artist, album FROM tracks"
        ).fetchall()
        conn.close()
        for row in rows:
            result[row["path"]] = {
                "year":     row["year"],
                "bpm":      row["bpm"],
                "duration": row["duration"],
                "artist":   row["artist"] or "",
                "album":    row["album"] or "",
            }
    except Exception:
        pass
    return result
