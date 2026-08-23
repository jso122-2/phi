# -*- coding: utf-8 -*-
"""phi.ui._genre_graph_utils — pure layout and rendering helpers for genre graph.

No Tkinter dependency — all functions operate on plain Python data structures.
``GenreGraphView`` imports these to keep its own file focused on UI wiring.
"""
from __future__ import annotations

import math
from typing import Optional


# ── Typography constants ───────────────────────────────────────────────────────

_FT: dict[str, tuple] = {
    "node":       ("Menlo", 12, "bold"),
    "label":      ("Menlo", 10, "bold"),
    "count":      ("Menlo", 8),
    "edge":       ("Menlo", 8),
    "sub_node":   ("Menlo", 9),
    "sub_lbl":    ("Menlo", 9),
    "sub_edge":   ("Menlo", 8),
    "sep":        ("Menlo", 7),
    "title":      ("Menlo", 16, "bold"),
    "crumb":      ("Menlo", 10),
    "crumb_k":    ("Menlo", 10),
    "crumb_s":    ("Menlo", 9),
    "sub":        ("Menlo", 11, "bold"),
    "mood":       ("Menlo", 10),
    "artist":     ("Menlo", 10),
    "track":      ("Menlo", 9),
    "play":       ("Menlo", 10, "bold"),
    "mini":       ("Menlo", 7),
    "mini_l":     ("Menlo", 7),
    "hint":       ("Menlo", 6),
    "conn":       ("Menlo", 9),
    "cursor_hl":  ("Menlo", 12, "bold"),
}

_G_ROWS       = 32
_G_COLS       = 90
_GENUS_HDR_H  = 12

_NODE_CH      = "◉"
_NODE_HOT_CH  = "◎"
_SUB_CH       = "○"
_EDGE_CH      = "·"
_SUB_EDGE_CH  = "╌"


# ── CharGrid ──────────────────────────────────────────────────────────────────

class _CharGrid:
    """Mutable 2-D monospace grid with per-cell tag for tk.Text annotation."""

    def __init__(self, rows: int, cols: int) -> None:
        self.rows = rows
        self.cols = cols
        self._ch  = [[" "] * cols for _ in range(rows)]
        self._tag = [[""]  * cols for _ in range(rows)]

    def put(self, r: int, c: int, ch: str, tag: str = "") -> None:
        """Write a single character at (r, c). Out-of-bounds writes are silently dropped."""
        if 0 <= r < self.rows and 0 <= c < self.cols:
            self._ch[r][c]  = ch
            self._tag[r][c] = tag

    def text(self, r: int, c: int, s: str, tag: str = "") -> None:
        """Write a string left-to-right starting at (r, c)."""
        for i, ch in enumerate(s):
            self.put(r, c + i, ch, tag)

    def line(
        self,
        r1: int, c1: int,
        r2: int, c2: int,
        ch:  str = _EDGE_CH,
        tag: str = "edge",
    ) -> None:
        """Bresenham line from (r1,c1) to (r2,c2)."""
        dr, dc = abs(r2 - r1), abs(c2 - c1)
        sr = 1 if r2 > r1 else -1
        sc = 1 if c2 > c1 else -1
        err = dr - dc
        r, c = r1, c1
        while True:
            self.put(r, c, ch, tag)
            if r == r2 and c == c2:
                break
            e2 = 2 * err
            if e2 > -dc:
                err -= dc
                r += sr
            if e2 < dr:
                err += dr
                c += sc

    def spans(self, ri: int) -> list[tuple[int, int, str]]:
        """Return list of (start, end, tag) runs for row *ri* (non-empty tags only)."""
        tags = self._tag[ri]
        if not tags:
            return []
        out: list[tuple[int, int, str]] = []
        s, cur = 0, tags[0]
        for i in range(1, len(tags)):
            if tags[i] != cur:
                if cur:
                    out.append((s, i, cur))
                s, cur = i, tags[i]
        if cur:
            out.append((s, len(tags), cur))
        return out

    def row(self, ri: int) -> str:
        """Return the character string for row *ri*."""
        return "".join(self._ch[ri])


# ── Layout helpers ─────────────────────────────────────────────────────────────

def _layout(genres: list[str], rows: int, cols: int) -> dict[str, tuple[int, int]]:
    """Circular/elliptical ring layout.

    Column radius ≈ 2× row radius to compensate for monospace aspect ratio.
    Node positions are clamped to leave room for labels on the right.

    Returns: {genre_name: (row, col)}
    """
    N = len(genres)
    if N == 0:
        return {}

    cr, cc = rows // 2, cols // 2
    max_label = max(len(g) for g in genres) + 6
    r_min, r_max = 2, rows - 3
    c_min, c_max = 2, cols - max_label - 2
    pos: dict[str, tuple[int, int]] = {}

    if N == 1:
        pos[genres[0]] = (cr, cc)
        return pos

    def _ring(subset: list[str], rr: int, rc: int, phase: float = 0.0) -> None:
        for i, g in enumerate(subset):
            angle = 2 * math.pi * i / len(subset) + phase
            r = max(r_min, min(r_max, int(cr + rr * math.sin(angle))))
            c = max(c_min, min(c_max, int(cc + rc * math.cos(angle))))
            pos[g] = (r, c)

    if N <= 8:
        _ring(genres, rr=int(rows * 0.36), rc=int((c_max - c_min) * 0.44))
    else:
        inner_n = max(3, N // 3)
        _ring(genres[:inner_n],
              rr=int(rows * 0.16), rc=int((c_max - c_min) * 0.20),
              phase=math.pi / max(1, inner_n))
        _ring(genres[inner_n:],
              rr=int(rows * 0.37), rc=int((c_max - c_min) * 0.44))
    return pos


def _genre_edges(
    tree: dict,
    pos:  dict[str, tuple[int, int]],
) -> list[tuple[str, str]]:
    """Connect genres by artist overlap; isolated nodes get a ring edge.

    Returns list of (genre_a, genre_b) pairs to draw as edges.
    """
    genre_artists: dict[str, set[str]] = {}
    for genre, sub_tree in tree.items():
        a: set[str] = set()
        for mood_tree in sub_tree.values():
            for art_tree in mood_tree.values():
                a.update(art_tree.keys())
        genre_artists[genre] = a

    result: list[tuple[str, str]] = []
    genres = list(pos.keys())
    for i, g1 in enumerate(genres):
        for g2 in genres[i + 1:]:
            if genre_artists.get(g1, set()) & genre_artists.get(g2, set()):
                result.append((g1, g2))
            if len(result) >= 24:
                break

    if not result:
        for i in range(len(genres)):
            result.append((genres[i], genres[(i + 1) % len(genres)]))
        return result

    return result


def _blend(bg: str, fg: str, t: float) -> str:
    """Linear interpolation between two CSS hex colours. Returns hex string.

    Args:
        bg: background hex colour (e.g. ``"#1a1a2e"``)
        fg: foreground hex colour
        t:  blend factor in [0, 1] — 0 = bg, 1 = fg

    Raises: ValueError if colour strings are malformed.
    """
    def _parse(c: str) -> tuple[int, int, int]:
        c = c.lstrip("#")
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)

    br, bg_r, bb = _parse(bg)
    fr, fg_r, fb = _parse(fg)
    r = int(br + (fr - br) * t)
    g = int(bg_r + (fg_r - bg_r) * t)
    b = int(bb + (fb - bb) * t)
    return f"#{r:02x}{g:02x}{b:02x}"
