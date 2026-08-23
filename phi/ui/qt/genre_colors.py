# -*- coding: utf-8 -*-
"""phi.ui.qt.genre_colors — deterministic genre → colour palette.

Used by PlaylistWidget and QueueRoom to paint per-track genre indicator dots.

Public API
----------
    GENRE_PALETTE               : list[str]   — 20 hex colours, dark-theme readable
    genre_color(genre)          : str         — deterministic colour for any genre string
    genres_from_meta(meta, ann) : list[str]   — parsed genres from meta/annotation dicts
    primary_genre_info(path, library) -> tuple[str, str]
                                — (hex_color, genre_label) for a track path
    build_genre_map(paths, library) -> dict[str, tuple[str, str]]
                                — {path: (hex_color, genre_label)} in one pass
    active_genres(genre_map)    -> list[tuple[str, str]]
                                — [(genre_label, hex_color), …] sorted — for the legend
"""
from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# ── Palette ────────────────────────────────────────────────────────────────────
# 20 visually distinct colours, calibrated for dark (#0d0d0d – #1a1a1a) backgrounds.
# Arranged so adjacent indices are maximally different (avoids runs of similar hues).

GENRE_PALETTE: list[str] = [
    "#7c9ee8",   #  0  indigo-blue    electronic / synth
    "#e8816e",   #  1  coral          rock / metal
    "#6ee8a0",   #  2  mint           hip-hop / rap
    "#e8c46e",   #  3  amber          jazz / soul
    "#c46ee8",   #  4  lilac          ambient / experimental
    "#6ee8e8",   #  5  cyan           house / techno / trance
    "#e86e9e",   #  6  rose           pop
    "#aee86e",   #  7  lime           reggae / afrobeat
    "#e8a06e",   #  8  peach          R&B / neo-soul
    "#6eb0e8",   #  9  sky            drum & bass / breakbeat
    "#e8e86e",   # 10  yellow         funk / disco
    "#9e6ee8",   # 11  violet         classical / orchestral
    "#6ee8c4",   # 12  seafoam        world / folk
    "#e86ec0",   # 13  pink           indie / alternative
    "#c4e86e",   # 14  yellow-green   country / bluegrass
    "#6e6ee8",   # 15  deep blue      industrial / noise
    "#e8a06e",   # 16  salmon         blues
    "#6ee86e",   # 17  green          reggaeton / latin
    "#e8c06e",   # 18  gold           gospel / gospel-soul
    "#8ce8e8",   # 19  pale cyan      new age / meditation
]

_DIM_GREY = "#4a4a4a"   # fallback for unknown / untagged tracks

# ── Genre string helpers ───────────────────────────────────────────────────────

_SPLIT = re.compile(r"[;/|,]+")


def _norm(raw: str) -> str:
    return raw.lower().strip()


def genres_from_meta(meta: dict, ann: dict | None = None) -> list[str]:
    """
    Extract normalised genre strings from a track's metadata + annotation dicts.

    Priority: meta["genre"] → ann["genre"] → ann["mb_genres"] → ann["lfm_tags"]
              → ann["discogs_genres"]

    Returns a de-duplicated ordered list (primary genre first).
    """
    out: list[str] = []
    seen: set[str] = set()
    ann = ann or {}

    def _add(raw: str | None) -> None:
        if not raw:
            return
        for part in _SPLIT.split(str(raw)):
            g = _norm(part)
            if g and g not in seen:
                out.append(g)
                seen.add(g)

    _add(meta.get("genre"))
    _add(ann.get("genre"))

    for key in ("mb_genres", "lfm_tags", "discogs_genres"):
        tags = ann.get(key) or []
        if isinstance(tags, str):
            tags = [tags]
        for t in tags:
            _add(str(t))

    return out


# ── Colour assignment ─────────────────────────────────────────────────────────


def genre_color(genre: str) -> str:
    """Return the deterministic palette colour for *genre*."""
    if not genre:
        return _DIM_GREY
    idx = int(hashlib.md5(genre.encode()).hexdigest(), 16) % len(GENRE_PALETTE)
    return GENRE_PALETTE[idx]


def _genre_label_from_raw(raw: str) -> str:
    """Normalise a raw genre string to a display label (Title Case)."""
    return raw.replace("-", " ").title()


def primary_genre_info(path: str, library) -> tuple[str, str]:
    """
    Return ``(hex_color, genre_label)`` for a track *path*.

    Uses in-memory meta first; falls back to annotation if genre is absent.
    Always fast — no extra SQLite reads when meta is warm.
    ``genre_label`` is empty string when no genre is known.
    """
    meta = (library.get_meta(path) or {}) if path else {}

    # Quick path: genre already in meta
    raw = meta.get("genre")
    if raw:
        g = _norm(str(raw).split(";")[0].split(",")[0].split("/")[0])
        if g:
            return genre_color(g), _genre_label_from_raw(g)

    # Slower path: check annotation for enriched tags
    try:
        ann = library.get_annotation(path) or {}
        gs  = genres_from_meta(meta, ann)
        if gs:
            return genre_color(gs[0]), _genre_label_from_raw(gs[0])
    except Exception:
        pass

    return _DIM_GREY, ""


def primary_color(path: str, library) -> str:
    """Return the primary genre hex colour for a track *path*.  (Compatibility wrapper.)"""
    return primary_genre_info(path, library)[0]


# ── Batch builder ─────────────────────────────────────────────────────────────


def build_genre_map(paths: list[str], library) -> dict[str, tuple[str, str]]:
    """
    Build a ``{path: (hex_color, genre_label)}`` mapping for all *paths* in one pass.

    Called once per ``PlaylistWidget._do_refresh`` / ``QueueRoom.refresh_queue``
    so the delegate never hits the library during painting and genre labels are
    available without a second round-trip.

    Annotations are read only when the meta dict lacks a "genre" field —
    this keeps the common case to a single in-memory lookup per track.
    """
    return {p: primary_genre_info(p, library) for p in paths}


# ── Legend helper ─────────────────────────────────────────────────────────────


def active_genres(genre_map: dict[str, tuple[str, str]]) -> list[tuple[str, str]]:
    """
    Return ``[(genre_label, hex_color), …]`` for all genres present in *genre_map*,
    sorted alphabetically by label.

    Unknown/untagged tracks (empty label or dim-grey colour) are excluded.
    """
    seen: dict[str, str] = {}   # hex → label (first occurrence wins)
    for _path, (hex_c, label) in genre_map.items():
        if hex_c not in seen and hex_c != _DIM_GREY and label:
            seen[hex_c] = label
    return sorted(seen.items(), key=lambda kv: kv[1])
