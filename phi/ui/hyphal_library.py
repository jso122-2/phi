# -*- coding: utf-8 -*-
"""phi.ui.hyphal_library — tree-building constants and helpers for GenreGraphView.

Shared by phi.ui.genre_graph (Tk) and phi.ui.qt.genre_graph (PySide6).

Tree structure produced by build_tree():

    tree[genre][subgenre_or_None][mood][artist] = [(path, title, dur_s), ...]

All leaf nodes are (path, title, dur_s) tuples where dur_s is a "M:SS" string.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Union

from phi.config import fmt_time


# ── ASCII tree characters ──────────────────────────────────────────────────────

_BR   = "└─ "   # branch-right  — last child connector
_BL   = "   "   # blank-left    — indent continuation after last child
_TK   = "│  "   # trunk         — indent continuation for non-last child
_LINE = "── "   # track marker  — not currently playing
_PLAY = "▶  "   # track marker  — currently playing

# ── breadcrumb separator (genre › subgenre) ───────────────────────────────────

_SEP = "  ›  "

# ── duration column (chars from start of line before dur_s is appended) ───────

_DUR_COL = 62

# ── mood display order ─────────────────────────────────────────────────────────
# Moods absent from this list sort to index 99 (alphabetical after known moods).

_MOOD_ORDER: list[str] = [
    "energetic",
    "happy",
    "upbeat",
    "chill",
    "calm",
    "melancholic",
    "sad",
    "dark",
    "intense",
    "angry",
    "romantic",
    "focus",
    "sleep",
    "other",
]


# ── helpers ───────────────────────────────────────────────────────────────────

def _leaf_count(node: Any) -> int:
    """Recursively count leaf nodes (track tuples) in a (possibly nested) dict/list."""
    if isinstance(node, list):
        return len(node)
    if isinstance(node, dict):
        return sum(_leaf_count(v) for v in node.values())
    return 1


def build_tree(library: Any) -> dict:
    """
    Build a nested genre/subgenre/mood/artist/track tree from *library*.

    Returns
    -------
    dict[genre, dict[subgenre | None, dict[mood, dict[artist, list[tuple]]]]]

    Each leaf list contains (path, title, dur_s) tuples.
    """
    # nested defaultdict so we can assign without KeyErrors
    tree: dict = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(list)
            )
        )
    )

    for path in library.playlist:
        meta: dict = library.meta_cache.get(path) or {}
        ann:  dict = library.annotations.get(path) or {}

        genre    = (meta.get("genre") or ann.get("genre") or "").strip() or "unknown"
        subgenre = (ann.get("subgenre") or "").strip() or None
        mood     = (
            ann.get("spotify_mood") or ann.get("mood") or meta.get("mood") or ""
        ).strip() or "other"
        artist   = (meta.get("artist") or "").strip() or "unknown artist"
        title    = (meta.get("title") or "").strip() or path.split("/")[-1]

        dur   = float(meta.get("duration") or 0.0)
        dur_s = fmt_time(dur)

        tree[genre][subgenre][mood][artist].append((path, title, dur_s))

    # Convert defaultdicts to plain dicts so callers can serialise / compare safely
    return {
        genre: {
            sub: {
                mood: dict(artist_dict)
                for mood, artist_dict in mood_dict.items()
            }
            for sub, mood_dict in sub_dict.items()
        }
        for genre, sub_dict in tree.items()
    }
