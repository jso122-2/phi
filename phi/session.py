# -*- coding: utf-8 -*-
"""phi.session — JSON state persistence (save / restore)."""
from __future__ import annotations
import json
import os
from phi.config import STATE_FILE

# Lightweight sidecar written after every track departure so ELO / completion
# stats survive unclean shutdowns without a full state.json rewrite.
_PLAY_STATS_FILE = STATE_FILE.parent / "play_stats.json"


def save(data: dict) -> None:
    """Write state dict to disk. Silent on failure."""
    try:
        STATE_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def restore() -> dict | None:
    """Read and return state dict, or None if unavailable / corrupt."""
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return None


def save_play_stats(play_stats: dict) -> None:
    """Persist play_stats (ELO, completion_rate, skip_count) to a crash-recovery sidecar.

    Called from a background thread after each track departure.  The sidecar is
    always >= state.json in recency; session_manager.load() merges both on startup.
    """
    try:
        _PLAY_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PLAY_STATS_FILE.write_text(json.dumps(play_stats, indent=2))
    except Exception:
        pass


def load_play_stats() -> dict:
    """Read crash-recovery play_stats sidecar.  Returns {} if absent or corrupt."""
    try:
        return json.loads(_PLAY_STATS_FILE.read_text())
    except Exception:
        return {}


def filter_existing(paths: list[str]) -> list[str]:
    """Return only paths that still exist on disk."""
    return [p for p in paths if os.path.isfile(p)]

# Related: graph_ingest, CommandOverlay._tab_complete
