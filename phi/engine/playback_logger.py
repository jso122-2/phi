# -*- coding: utf-8 -*-
"""phi.engine.playback_logger — JSONL playback event log.

Writes one JSON object per line to ``~/.phi/logs/playback_YYYY-MM-DD.jsonl``
with daily rotation. Writes are buffered (flushed every 10 events OR 30 s)
and fully thread-safe.

ZoneClusterer (Phase 2) reads these files to build the zone → zone transition
matrix from real listening history.

Event schema
------------
  play  {"ts": float, "event": "play",  "path": str, "d4_a": float|null, "zone_id": int|null}
  skip  {"ts": float, "event": "skip",  "path": str, "pos": float}
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import IO, Any

from phi.config import PHI_DIR

_LOG_DIR       = PHI_DIR / "logs"
_FLUSH_EVERY_N = 10
_FLUSH_EVERY_S = 30.0


class PlaybackLogger:
    """Write playback events to a daily-rotating JSONL log in ``~/.phi/logs/``.

    Args:
        log_dir: Override the log directory (defaults to ``~/.phi/logs``).
                 Directory is created on first write if absent.
    """

    def __init__(self, log_dir: Path | None = None) -> None:
        self._dir: Path = Path(log_dir) if log_dir else _LOG_DIR
        self._lock: threading.Lock = threading.Lock()
        self._buf: list[str] = []
        self._last_flush: float = time.monotonic()
        self._fh: IO[str] | None = None
        self._current_day: str = ""

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_dir(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)

    def _get_fh(self) -> IO[str]:
        """Return the file handle for today, opening/rotating as needed."""
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._current_day:
            if self._fh is not None:
                try:
                    self._fh.close()
                except OSError:
                    pass
            self._ensure_dir()
            path = self._dir / f"playback_{today}.jsonl"
            self._fh = open(path, "a", encoding="utf-8")
            self._current_day = today
        assert self._fh is not None
        return self._fh

    def _append(self, record: dict[str, Any]) -> None:
        """Serialise *record* and append to the buffer; auto-flush as needed."""
        line = json.dumps(record, separators=(",", ":"))
        with self._lock:
            self._buf.append(line)
            now = time.monotonic()
            should_flush = (
                len(self._buf) >= _FLUSH_EVERY_N
                or (now - self._last_flush) >= _FLUSH_EVERY_S
            )
            if should_flush:
                self._flush_locked()

    def _flush_locked(self) -> None:
        """Write buffer to disk. Caller must hold ``self._lock``."""
        if not self._buf:
            return
        fh = self._get_fh()
        fh.write("\n".join(self._buf) + "\n")
        fh.flush()
        self._buf.clear()
        self._last_flush = time.monotonic()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(self, path: str, meta: dict[str, Any] | None = None) -> None:
        """Append a ``play`` event.

        Args:
            path: Track file path.
            meta: Optional metadata dict; ``d4_a`` and ``zone_id`` are
                  extracted if present.
        """
        m = meta or {}
        self._append({
            "ts":      time.time(),
            "event":   "play",
            "path":    path,
            "d4_a":    m.get("d4_a"),
            "zone_id": m.get("zone_id"),
        })

    def record_skip(self, path: str, pos: float) -> None:
        """Append a ``skip`` event (track abandoned before 30 % completion).

        Args:
            path: Track file path.
            pos:  Playback position in seconds at skip time.
        """
        self._append({
            "ts":    time.time(),
            "event": "skip",
            "path":  path,
            "pos":   round(pos, 2),
        })

    def flush(self) -> None:
        """Force an immediate flush to disk."""
        with self._lock:
            self._flush_locked()

    def close(self) -> None:
        """Flush and close the log file handle."""
        with self._lock:
            self._flush_locked()
            if self._fh is not None:
                try:
                    self._fh.close()
                except OSError:
                    pass
                self._fh = None
