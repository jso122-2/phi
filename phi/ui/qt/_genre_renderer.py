# -*- coding: utf-8 -*-
"""phi.ui.qt._genre_renderer — render mixin for GenreGraphView.

Supplies all _render_* / _emit / _highlight methods.
Relies on instance state set up by GenreGraphView.__init__ (no standalone use).
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit

from phi.config import CARD
from phi.ui._genre_graph_utils import (
    _CharGrid,
    _EDGE_CH,
    _G_COLS,
    _G_ROWS,
    _GENUS_HDR_H,
    _NODE_CH,
    _NODE_HOT_CH,
    _SUB_CH,
    _SUB_EDGE_CH,
)
from phi.ui.hyphal_library import _leaf_count
from phi.ui.hyphal_library import (
    _BL,
    _BR,
    _DUR_COL,
    _LINE,
    _MOOD_ORDER,
    _PLAY,
    _SEP,
    _TK,
)

if TYPE_CHECKING:
    pass


class _GenreRenderMixin:
    """
    Rendering-only methods for GenreGraphView.

    Expected instance attributes (set by GenreGraphView.__init__):
        _t              : QTextEdit
        _tree           : dict
        _pos            : dict
        _edge_pairs     : list
        _graph_nodes    : list
        _graph_cursor_idx : int
        _focus          : list
        _path_lines     : dict
        _line_paths     : dict
        _genre_lines    : dict
        _sub_lines      : dict
        _node_cols      : dict
        _sat_map        : dict
        _section_lines  : list
        _playing        : Optional[str]
        _cursor         : Optional[str]
        _line_no        : int
        _qcursor        : QTextCursor
        _fmt_cache      : dict
        _default_fmt    : QTextCharFormat  (property)
        _fmt(tag)       : method
    """

    # ── render dispatch ───────────────────────────────────────────────────────

    def _render(self) -> None:
        self._path_lines.clear()
        self._line_paths.clear()
        self._genre_lines.clear()
        self._sub_lines.clear()
        self._node_cols.clear()
        self._sat_map.clear()
        self._section_lines.clear()
        self._line_no = 1

        self._t.setReadOnly(False)
        self._t.clear()
        self._qcursor = QTextCursor(self._t.document())

        if not self._tree:
            self._emit("  no tracks loaded  ·  add a folder to begin\n",
                       [(0, 999, "hint")])
        else:
            depth = len(self._focus)
            if depth == 0:
                self._render_graph()
            elif depth == 1:
                self._render_genus(self._focus[0])
            else:
                self._render_species(self._focus[0], self._focus[1])

            self._emit("\n", [])
            self._emit(
                "  f · ← zoom out   ↑↓ iw  navigate   d enter  play   "
                "h zoom in   e next section   k+s tab\n",
                [(0, 999, "hint")],
            )

        self._t.setReadOnly(True)

        if self._cursor and self._cursor in self._path_lines:
            self._highlight(self._cursor)

    # ── level 0: spatial genre graph ─────────────────────────────────────────

    def _render_graph(self) -> None:
        grid = _CharGrid(_G_ROWS, _G_COLS)
        hot  = (
            self._graph_nodes[self._graph_cursor_idx]
            if self._graph_nodes else None
        )

        for g1, g2 in self._edge_pairs:
            p1, p2 = self._pos.get(g1), self._pos.get(g2)
            if p1 and p2:
                grid.line(p1[0], p1[1], p2[0], p2[1], _EDGE_CH, "edge")

        for genre, (r, c) in self._pos.items():
            subs = sorted(k for k in self._tree[genre] if k is not None)[:4]
            if subs:
                sat_r    = r + 1
                text_parts: list[tuple[int, int, str]] = []
                col_cur  = c + 1
                for sub in subs:
                    short = sub[:7]
                    cs    = col_cur
                    ce    = cs + 1 + 1 + len(short)
                    text_parts.append((cs, ce, sub))
                    col_cur = ce + 2
                for cs, ce, sub in text_parts:
                    grid.put(sat_r, cs, _SUB_CH, "sub_node")
                    grid.text(sat_r, cs + 1, " " + sub[:7], "sub_lbl")
                self._sat_map[sat_r] = [
                    (cs, ce, genre, sub) for (cs, ce, sub) in text_parts
                ]

        for genre, (r, c) in self._pos.items():
            is_hot = (genre == hot)
            glyph  = _NODE_HOT_CH if is_hot else _NODE_CH
            n_tag  = "node_hot" if is_hot else "node"
            l_tag  = "label_hot" if is_hot else "label"
            count  = _leaf_count(self._tree[genre])
            grid.put(r, c, glyph, n_tag)
            grid.text(r, c + 1, f" {genre}", l_tag)
            grid.text(r, c + 2 + len(genre), f"  ·{count}", "count")
            self._node_cols[genre] = c

        for ri in range(_G_ROWS):
            row_text = grid.row(ri) + "\n"
            ln       = self._line_no
            spans    = grid.spans(ri)
            self._emit(row_text, spans)

            for genre, (gr, _) in self._pos.items():
                if gr == ri:
                    self._genre_lines[genre] = ln
                    self._section_lines.append(ln)

            if ri in self._sat_map:
                entries = self._sat_map.pop(ri)
                self._sat_map[ln] = entries

        self._section_lines.sort()

    # ── level 1: genus ────────────────────────────────────────────────────────

    def _render_genus(self, genre: str) -> None:
        sub_tree = self._tree.get(genre, {})
        subs     = sorted(k for k in sub_tree if k is not None)
        direct   = sub_tree.get(None)

        hdr    = _CharGrid(_GENUS_HDR_H, _G_COLS)
        gcount = _leaf_count(self._tree[genre])
        hcr, hcc = 1, _G_COLS // 2
        hdr.put(hcr, hcc, _NODE_CH, "node")
        hdr.text(hcr, hcc + 1, f" {genre}", "title")
        hdr.text(hcr, hcc + 2 + len(genre), f"  ·{gcount}", "count")

        sub_node_rows: list[tuple[int, int, str]] = []
        n = len(subs[:6])
        for si, sub in enumerate(subs[:6]):
            angle = 0.0 if n == 1 else math.pi * (si / (n - 1) - 0.5) * 1.3
            sr = hcr + 5 + int(abs(math.sin(angle)) * 3)
            sc = int(hcc + 16 * math.sin(angle))
            sc = max(2, min(_G_COLS - len(sub) - 6, sc))
            sub_count = _leaf_count(sub_tree[sub])
            hdr.put(sr, sc, _SUB_CH, "sub_node")
            hdr.text(sr, sc + 1, f" {sub}  ·{sub_count}", "crumb_k")
            hdr.line(hcr, hcc, sr, sc, _SUB_EDGE_CH, "sub_edge")
            hdr.put(sr, sc, _SUB_CH, "sub_node")
            sub_node_rows.append((sr, sc, sub))

        hdr.text(_GENUS_HDR_H - 1, 0,
                 " " * 2 + _SUB_EDGE_CH * (_G_COLS - 4), "sep")

        self._genre_lines[genre] = self._line_no
        for ri in range(_GENUS_HDR_H):
            ln   = self._line_no
            self._emit(hdr.row(ri) + "\n", hdr.spans(ri))
            for (sr, sc, sub) in sub_node_rows:
                if sr == ri:
                    key = f"{genre}\x00{sub}"
                    self._sub_lines[key] = ln
                    self._section_lines.append(ln)

        self._emit("\n", [])
        all_subs = [(k, sub_tree[k]) for k in subs]
        if direct:
            all_subs.append((None, direct))

        for si, (sub, mood_tree) in enumerate(all_subs):
            self._render_sub_block(
                genre, sub, mood_tree, ["  "],
                is_last=(si == len(all_subs) - 1),
            )

        others  = sorted(g for g in self._tree if g != genre and "unknown" not in g)
        unknown = [g for g in self._tree if g != genre and "unknown" in g]
        for g in others + unknown:
            self._emit("\n", [])
            cnt = _leaf_count(self._tree[g])
            self._genre_lines[g] = self._line_no
            self._section_lines.append(self._line_no)
            self._emit(f"  {g}  ·  {cnt}\n", [(0, 999, "mini_l")])

        self._section_lines.sort()

    # ── level 2: species ──────────────────────────────────────────────────────

    def _render_species(self, genre: str, subgenre: str) -> None:
        sub_tree  = self._tree.get(genre, {})
        mood_tree = sub_tree.get(subgenre) or sub_tree.get(None, {})

        self._emit("\n", [])
        bc      = f"  {genre}{_SEP}{subgenre}"
        g_end   = 2 + len(genre)
        sep_end = g_end + len(_SEP)
        sub_end = sep_end + len(subgenre)
        self._genre_lines[genre] = self._line_no
        self._section_lines.append(self._line_no)
        self._emit(bc + "\n", [
            (2,       g_end,   "crumb_k"),
            (g_end,   sep_end, "crumb_s"),
            (sep_end, sub_end, "crumb_k"),
        ])
        self._emit("\n", [])
        self._emit(f"  {subgenre}\n", [(2, 2 + len(subgenre), "sub")])
        self._emit("\n", [])

        moods = sorted(
            mood_tree.keys(),
            key=lambda m: _MOOD_ORDER.index(m) if m in _MOOD_ORDER else 99,
        )
        for mi, mood in enumerate(moods):
            self._render_mood_block(
                mood, mood_tree[mood], ["  "],
                is_last=(mi == len(moods) - 1),
            )

        other_subs = sorted(k for k in sub_tree if k is not None and k != subgenre)
        if other_subs:
            self._emit("\n", [])
            for sub in other_subs:
                cnt = _leaf_count(sub_tree[sub])
                k   = f"{genre}\x00{sub}"
                self._sub_lines[k] = self._line_no
                self._section_lines.append(self._line_no)
                self._emit(f"  {sub}  ·  {cnt}\n", [(0, 999, "mini")])

        others  = sorted(g for g in self._tree if g != genre and "unknown" not in g)
        unknown = [g for g in self._tree if g != genre and "unknown" in g]
        for g in others + unknown:
            self._emit("\n", [])
            cnt = _leaf_count(self._tree[g])
            self._genre_lines[g] = self._line_no
            self._section_lines.append(self._line_no)
            self._emit(f"  {g}  ·  {cnt}\n", [(0, 999, "mini")])

        self._section_lines.sort()

    # ── sub-render helpers ────────────────────────────────────────────────────

    def _render_sub_block(
        self,
        genre:     str,
        sub:       Optional[str],
        mood_tree: dict,
        anc:       list[str],
        is_last:   bool,
    ) -> None:
        base = "".join(anc)
        if sub is not None:
            k    = f"{genre}\x00{sub}"
            self._sub_lines[k] = self._line_no
            conn = base + _BR
            self._emit(conn + sub + "\n", [
                (0, len(conn), "conn"),
                (len(conn), len(conn) + len(sub), "crumb_k"),
            ])
            child_anc = anc + [_BL if is_last else _TK]
        else:
            child_anc = anc

        moods = sorted(
            mood_tree.keys(),
            key=lambda m: _MOOD_ORDER.index(m) if m in _MOOD_ORDER else 99,
        )
        for mi, mood in enumerate(moods):
            self._render_mood_block(
                mood, mood_tree[mood], child_anc,
                is_last=(mi == len(moods) - 1),
            )

    def _render_mood_block(
        self,
        mood:     str,
        art_tree: dict,
        anc:      list[str],
        is_last:  bool,
    ) -> None:
        base = "".join(anc)
        conn = base + _BR
        lbl  = f"[{mood}]"
        self._emit(conn + lbl + "\n", [
            (0, len(conn), "conn"),
            (len(conn), len(conn) + len(lbl), "mood"),
        ])
        child_anc = anc + [_BL if is_last else _TK]
        for ai, artist in enumerate(sorted(art_tree.keys(), key=str.lower)):
            self._render_artist_block(
                artist, art_tree[artist], child_anc,
                is_last=(ai == len(art_tree) - 1),
            )

    def _render_artist_block(
        self,
        artist:  str,
        tracks:  list,
        anc:     list[str],
        is_last: bool,
    ) -> None:
        base = "".join(anc)
        conn = base + _BR
        self._emit(conn + artist + "\n", [
            (0, len(conn), "conn"),
            (len(conn), len(conn) + len(artist), "artist"),
        ])
        child_anc = anc + [_BL if is_last else _TK]
        for ti, (path, title, dur_s) in enumerate(tracks):
            self._render_track_leaf(
                path, title, dur_s, child_anc,
                is_last=(ti == len(tracks) - 1),
            )

    def _render_track_leaf(
        self,
        path:    str,
        title:   str,
        dur_s:   str,
        anc:     list[str],
        is_last: bool,
    ) -> None:
        base    = "".join(anc)
        conn    = base + _BR
        playing = path == self._playing
        marker  = _PLAY if playing else _LINE

        pre_len   = len(conn) + len(marker)
        title_max = _DUR_COL - pre_len - 1
        if len(title) > title_max:
            title = title[: title_max - 1] + "…"
        pad  = " " * max(1, _DUR_COL - pre_len - len(title))
        line = conn + marker + title + pad + dur_s

        conn_end   = len(conn)
        marker_end = conn_end + len(marker)
        title_end  = marker_end + len(title)
        pad_end    = title_end + len(pad)

        spans = [
            (0,         conn_end,             "conn"),
            (title_end, pad_end,              "conn"),
            (pad_end,   pad_end + len(dur_s), "dur"),
        ]
        if playing:
            spans += [(conn_end, marker_end, "play"), (marker_end, title_end, "play")]
        else:
            spans.append((marker_end, title_end, "track"))

        ln = self._line_no
        self._emit(line + "\n", spans)
        self._path_lines[path] = ln
        self._line_paths[ln]   = path

    # ── text helper ───────────────────────────────────────────────────────────

    def _emit(self, text: str, spans: list[tuple[int, int, str]]) -> None:
        """Insert *text* into the document with colored spans."""
        n = len(text)
        if not spans:
            self._qcursor.insertText(text, self._default_fmt)
        else:
            sorted_spans = sorted(spans, key=lambda x: x[0])
            pos = 0
            for start, end, tag in sorted_spans:
                if start > pos:
                    self._qcursor.insertText(text[pos:start], self._default_fmt)
                end_clamped = min(end, n)
                if end_clamped > start:
                    self._qcursor.insertText(text[start:end_clamped], self._fmt(tag))
                pos = end_clamped
            if pos < n:
                self._qcursor.insertText(text[pos:], self._default_fmt)

        if text.endswith("\n"):
            self._line_no += 1

    # ── highlight ─────────────────────────────────────────────────────────────

    def _highlight(self, path: str) -> None:
        ln = self._path_lines.get(path)
        if not ln:
            self._t.setExtraSelections([])
            return

        doc    = self._t.document()
        block  = doc.findBlockByNumber(ln - 1)
        cursor = QTextCursor(block)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock,
            QTextCursor.MoveMode.KeepAnchor,
        )

        fmt = QTextCharFormat()
        fmt.setBackground(QColor(CARD))

        sel           = QTextEdit.ExtraSelection()
        sel.format    = fmt
        sel.cursor    = cursor
        self._t.setExtraSelections([sel])

        scroll_cursor = QTextCursor(block)
        self._t.setTextCursor(scroll_cursor)
        self._t.ensureCursorVisible()
