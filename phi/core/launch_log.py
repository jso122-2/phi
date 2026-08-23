# -*- coding: utf-8 -*-
"""phi.core.launch_log — append-only per-launch cache snapshot.

Writes one JSON line to ``~/.phi/launches.jsonl`` every time phi starts.
Each entry captures the state of every persistent cache so you can audit
what was loaded, enriched, and rate-limited across sessions.

Schema (one JSON object per line)
──────────────────────────────────
{
  "ts":            "2026-07-19T09:05:30.123456",   # ISO-8601 launch time
  "library_size":  1234,                            # tracks in session playlist
  "meta_tracks":   1190,                            # rows in meta.db tracks table
  "annotated":     874,                             # tracks with ≥1 annotation
  "playlists":     12,                              # named playlists in DB
  "queue_pos":     42,                              # restored queue position
  "volume":        0.72,
  "spotify": {
    "configured":    true,
    "cache_path":    "/Users/…/.phi/spotify_token.cache",
    "token_cached":  true,                          # token file exists on disk
    "rate_limited":  false                          # spotipy backoff active?
  },
  "session_file":  "/Users/…/.phi/state.json",
  "meta_db":       "/Users/…/.phi/meta.db",
  "log_file":      "/Users/…/.phi/phi.log"
}
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phi.ui.qt.app import PhiMainWindow as PhiApp

_log = logging.getLogger("phi.launch_log")

_PHI_DIR   = Path.home() / ".phi"
_LAUNCHES  = _PHI_DIR / "launches.jsonl"
_STATE_JSON = _PHI_DIR / "state.json"
_META_DB    = _PHI_DIR / "meta.db"
_PHI_LOG    = _PHI_DIR / "phi.log"
_SPOT_CACHE = _PHI_DIR / "spotify_token.cache"


# ── helpers ───────────────────────────────────────────────────────────────────

def _meta_stats() -> dict:
    """Query meta.db for track / annotation counts without touching MetaCache."""
    out = {"meta_tracks": 0, "annotated": 0, "playlists": 0}
    if not _META_DB.exists():
        return out
    try:
        conn = sqlite3.connect(str(_META_DB), timeout=2)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM tracks")
            out["meta_tracks"] = cur.fetchone()[0]

            # annotation table name varies — try both schemas
            for tbl in ("annotations", "track_annotations"):
                try:
                    cur.execute(
                        f"SELECT COUNT(DISTINCT path) FROM {tbl}"
                    )
                    out["annotated"] = cur.fetchone()[0]
                    break
                except sqlite3.OperationalError:
                    pass

            try:
                cur.execute("SELECT COUNT(*) FROM playlists")
                out["playlists"] = cur.fetchone()[0]
            except sqlite3.OperationalError:
                pass
        conn.close()
    except Exception as exc:
        _log.debug("launch_log: meta_stats failed: %s", exc)
    return out


def _session_snapshot() -> dict:
    """Read state.json without instantiating any app objects."""
    out = {"queue_pos": 0, "volume": 0.7, "library_size": 0}
    if not _STATE_JSON.exists():
        return out
    try:
        data = json.loads(_STATE_JSON.read_text(encoding="utf-8"))
        out["queue_pos"]    = int(data.get("queue_pos", 0))
        out["volume"]       = float(data.get("volume", 0.7))
        out["library_size"] = len(data.get("playlist", []))
    except Exception as exc:
        _log.debug("launch_log: session_snapshot failed: %s", exc)
    return out


def _spotify_snapshot() -> dict:
    """Check Spotify token-cache state without making any network calls."""
    out = {
        "configured":   False,
        "cache_path":   str(_SPOT_CACHE),
        "token_cached": False,
        "rate_limited": False,
    }
    try:
        from phi.config import load_phi_config
        cfg = load_phi_config().get("spotify", {})
        out["configured"] = bool(cfg.get("client_id") and cfg.get("client_secret"))
    except Exception:
        pass

    if _SPOT_CACHE.exists():
        out["token_cached"] = True
        try:
            token_data = json.loads(_SPOT_CACHE.read_text(encoding="utf-8"))
            # spotipy cache format has a "retries" / "Retry-After" key when limited
            if token_data.get("Retry-After") or token_data.get("retry_after"):
                out["rate_limited"] = True
        except Exception:
            pass

    return out


# ── public API ────────────────────────────────────────────────────────────────

def record(app: "PhiApp | None" = None) -> Path:
    """
    Write one launch entry to ``~/.phi/launches.jsonl``.

    Pass *app* to pull live library/queue data; omit to read from files only
    (useful if called before PhiApp is fully constructed).

    Returns the path to the launches file.
    """
    _PHI_DIR.mkdir(parents=True, exist_ok=True)

    entry: dict = {
        "ts": datetime.now(tz=timezone.utc).isoformat(),
        **_session_snapshot(),
        **_meta_stats(),
        "spotify":      _spotify_snapshot(),
        "session_file": str(_STATE_JSON),
        "meta_db":      str(_META_DB),
        "log_file":     str(_PHI_LOG),
        "launches_file": str(_LAUNCHES),
    }

    # Override library_size with live data when app is available
    if app is not None:
        try:
            entry["library_size"] = app.library.size
            entry["queue_pos"]    = app.queue.pos
            entry["volume"]       = round(getattr(app.player, "volume", entry["volume"]), 3)
        except Exception as exc:
            _log.debug("launch_log: live app snapshot failed: %s", exc)

    try:
        with _LAUNCHES.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception as exc:
        _log.warning("launch_log: could not write to %s: %s", _LAUNCHES, exc)
        return _LAUNCHES

    _log.info(
        "launch recorded — library=%d  meta=%d  annotated=%d  playlists=%d  "
        "spotify_ok=%s  → %s",
        entry["library_size"],
        entry["meta_tracks"],
        entry["annotated"],
        entry["playlists"],
        entry["spotify"]["configured"] and not entry["spotify"]["rate_limited"],
        _LAUNCHES,
    )
    return _LAUNCHES
