# -*- coding: utf-8 -*-
"""
phi.config — application constants, helpers, and config loader.

Colour palette
--------------
All colours live in ``phi.ui.style`` (the single source of styling truth).
They are re-exported here so existing ``from phi.config import BG, ACC, …``
imports continue to work unchanged.

To change a colour: edit ``phi/ui/style.py``, nowhere else.
"""
from __future__ import annotations
import pathlib

# ── re-export the full palette from the immutable stylesheet ──────────────────
# UI files may import from either `phi.config` (legacy) or `phi.ui.style`
# (preferred).  Both resolve to the same frozen PhiPalette values.
from phi.ui.style import (  # noqa: F401  (re-exported for callers)
    PALETTE,
    BG, CARD, CARD2, BORDER,
    ACC, GOLD, ACC2,
    INDIGO, VIOLET,
    FG, MUTED, NOW,
    METER_OK, METER_WARN, METER_CRIT,
    ENTRY_BG, ENTRY_FG,
)

# ── sort / layout ─────────────────────────────────────────────────────────────
SORT_KEYS = ("title", "artist", "album", "duration")
ART_SIZE  = 80

# ── audio ─────────────────────────────────────────────────────────────────────
AUDIO_EXTS     = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"}
CROSSFADE_SECS = 3.0    # crossfade duration in seconds; set to 0 to disable
GAPLESS        = True   # use pygame.queue() for gapless when crossfade is off

# ── queue ─────────────────────────────────────────────────────────────────────
REPEAT_STATES = ("off", "all", "one")

# ── persistence ───────────────────────────────────────────────────────────────
PHI_DIR       = pathlib.Path.home() / ".phi"
STATE_FILE    = PHI_DIR / "state.json"
META_DB       = PHI_DIR / "meta.db"    # SQLite metadata + annotation cache
WATCH_POLL_MS = 2_000                  # folder-watcher scan interval (ms)
POLL_MS       = 100                    # main UI poll interval (ms)


# ── pure helpers ──────────────────────────────────────────────────────────────

def fmt_time(s: float) -> str:
    """Format seconds as M:SS string."""
    s = max(0, int(s))
    return f"{s // 60}:{s % 60:02d}"


def vol_icon(v: float) -> str:
    """Return the appropriate volume emoji for the given level (0–1)."""
    if v == 0:   return "[M]"
    if v < 0.4:  return "[v]"
    return "[V]"


# ── phi_config.yaml loader ────────────────────────────────────────────────────

_PHI_CONFIG_PATH  = pathlib.Path(__file__).parent.parent / "phi_config.yaml"
_phi_config_cache: dict | None = None


def load_phi_config() -> dict:
    """
    Load phi_config.yaml from the phi package directory.
    Returns an empty dict if the file is missing or unreadable.
    Results are cached after the first load.
    """
    global _phi_config_cache
    if _phi_config_cache is not None:
        return _phi_config_cache

    if not _PHI_CONFIG_PATH.exists():
        _phi_config_cache = {}
        return _phi_config_cache

    try:
        import yaml
        with open(_PHI_CONFIG_PATH, encoding="utf-8") as f:
            _phi_config_cache = yaml.safe_load(f) or {}
    except Exception:
        _phi_config_cache = {}

    return _phi_config_cache


def enrich_config() -> dict:
    """Return the meta_enrichment section of phi_config.yaml."""
    return load_phi_config().get("meta_enrichment", {})
