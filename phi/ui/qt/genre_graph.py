# -*- coding: utf-8 -*-
"""phi.ui.qt.genre_graph — PySide6 full-page ASCII genre network with fractal zoom.

Public API (mirrors GenreGraphView from phi.ui.genre_graph):
    rebuild()
    redraw()
    mark_playing(path)
    on_focus()
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat
from PySide6.QtWidgets import (
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from phi.config import ACC, ACC2, BG, CARD, FG, MUTED
from phi.ui._genre_graph_utils import (
    _FT,
    _G_COLS,
    _G_ROWS,
    _blend,
    _genre_edges,
    _layout,
)
from phi.ui.hyphal_library import _leaf_count
from phi.ui.hyphal_library import build_tree
from phi.ui.genre_graph import write_jim_bindings
from phi.ui.qt._genre_renderer import _GenreRenderMixin


# ── colour palette ────────────────────────────────────────────────────────────

_C      = _blend(BG, MUTED, 0.28)
_C_EDGE = _blend(BG, MUTED, 0.18)

_TAG_COLOR: dict[str, str] = {
    "node":      ACC,
    "node_hot":  FG,
    "label":     FG,
    "label_hot": ACC,
    "count":     MUTED,
    "edge":      _C,
    "sub_node":  ACC2,
    "sub_lbl":   _C,
    "sub_edge":  _C_EDGE,
    "sep":       _C,
    "title":     FG,
    "crumb":     MUTED,
    "crumb_k":   ACC2,
    "crumb_s":   _C,
    "sub":       FG,
    "mood":      ACC2,
    "artist":    MUTED,
    "track":     FG,
    "dur":       _C,
    "conn":      _C,
    "play":      ACC,
    "mini":      _C,
    "mini_l":    MUTED,
    "hint":      _C,
    "cursor":    CARD,
}

_BOLD_TAGS = {"node", "node_hot", "title", "play", "crumb_k", "sub", "label"}


# ── inner text widget ─────────────────────────────────────────────────────────

class _GenreText(QTextEdit):
    """Read-only text surface; delegates mouse + key events to GenreGraphView."""

    def __init__(self, view: "GenreGraphView", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view = view

    def mousePressEvent(self, event) -> None:
        cursor  = self.cursorForPosition(event.pos())
        line_no = cursor.blockNumber() + 1
        col_no  = cursor.positionInBlock()
        self._view._click_at(line_no, col_no)

    def wheelEvent(self, event) -> None:
        super().wheelEvent(event)

    def keyPressEvent(self, event) -> None:
        self._view.keyPressEvent(event)


# ── GenreGraphView ────────────────────────────────────────────────────────────

class GenreGraphView(_GenreRenderMixin, QWidget):
    """
    Full-page ASCII genre graph with fractal zoom.

    ctrl must expose:
        ctrl.library            Library instance
        ctrl.on_play_path(path) immediately play a path
    """

    def __init__(self, ctrl: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctrl = ctrl

        self._tree:       dict                       = {}
        self._pos:        dict[str, tuple[int, int]] = {}
        self._edge_pairs: list[tuple[str, str]]      = []

        self._graph_nodes:       list[str] = []
        self._graph_cursor_idx:  int       = 0

        self._focus: list[str] = []

        self._path_lines:    dict[str, int]    = {}
        self._line_paths:    dict[int, str]    = {}
        self._genre_lines:   dict[str, int]    = {}
        self._sub_lines:     dict[str, int]    = {}
        self._node_cols:     dict[str, int]    = {}
        self._sat_map:       dict[int, list[tuple[int, int, str, str]]] = {}
        self._section_lines: list[int]         = []

        self._playing: Optional[str] = None
        self._cursor:  Optional[str] = None
        self._line_no: int           = 1

        self._k_held = False

        self._fmt_cache: dict[str, QTextCharFormat] = {}

        write_jim_bindings()
        self._build()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._t = _GenreText(view=self, parent=self)
        self._t.setReadOnly(True)
        self._t.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self._t.setStyleSheet(
            f"QTextEdit {{ background: {BG}; color: {FG}; border: none; "
            f"font-family: Menlo, Courier, monospace; font-size: 9px; "
            f"padding: 16px 20px; }}"
        )
        self._t.setFont(QFont("Menlo", 9))
        self._t.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        layout.addWidget(self._t)
        self.setFocusProxy(self._t)

    # ── format helpers ────────────────────────────────────────────────────────

    def _fmt(self, tag: str) -> QTextCharFormat:
        if tag not in self._fmt_cache:
            f = QTextCharFormat()
            color = _TAG_COLOR.get(tag, FG)
            f.setForeground(QColor(color))
            if tag in _BOLD_TAGS:
                f.setFontWeight(QFont.Weight.Bold)
            else:
                f.setFontWeight(QFont.Weight.Normal)
            self._fmt_cache[tag] = f
        return self._fmt_cache[tag]

    @property
    def _default_fmt(self) -> QTextCharFormat:
        return self._fmt("")

    # ── public API ────────────────────────────────────────────────────────────

    def rebuild(self) -> None:
        self._tree = build_tree(self._ctrl.library)  # type: ignore[union-attr]
        genres     = sorted(self._tree.keys(), key=lambda g: ("unknown" in g, g))
        self._pos  = _layout(genres, _G_ROWS, _G_COLS)
        self._edge_pairs      = _genre_edges(self._tree, self._pos)
        self._graph_nodes     = genres
        self._graph_cursor_idx = min(
            self._graph_cursor_idx, max(0, len(genres) - 1)
        )
        if self._focus and self._focus[0] not in self._tree:
            self._focus = []
        self._render()

    def redraw(self) -> None:
        """Re-render from cached _tree without calling build_tree()."""
        if self._tree:
            self._render()

    def mark_playing(self, path: Optional[str]) -> None:
        self._playing = path
        if self._tree and self.isVisible():
            self._render()

    def on_focus(self) -> None:
        self.redraw()

    # ── navigation helpers ────────────────────────────────────────────────────

    def _zoom_in(self, genre: str, sub: Optional[str] = None) -> None:
        self._focus = [genre, sub] if sub is not None else [genre]
        self._render()

    def _zoom_out(self) -> None:
        if len(self._focus) > 1:
            self._focus = self._focus[:1]
        elif self._focus:
            self._focus = []
        self._render()

    def _leaf_paths(self) -> list[str]:
        return [self._line_paths[ln] for ln in sorted(self._line_paths)]

    def _cursor_idx(self) -> int:
        leaves = self._leaf_paths()
        return leaves.index(self._cursor) if self._cursor in leaves else -1

    def _move_cursor(self, delta: int) -> None:
        from PySide6.QtGui import QTextCursor as _QTC
        leaves = self._leaf_paths()
        if not leaves:
            return
        idx = self._cursor_idx()
        idx = max(0, min(len(leaves) - 1, (0 if idx < 0 else idx) + delta))
        self._cursor = leaves[idx]
        self._highlight(self._cursor)

    def _move_graph_cursor(self, delta: int) -> None:
        from PySide6.QtGui import QTextCursor as _QTC
        if not self._graph_nodes:
            return
        self._graph_cursor_idx = (
            self._graph_cursor_idx + delta
        ) % len(self._graph_nodes)
        self._render()
        genre = self._graph_nodes[self._graph_cursor_idx]
        ln    = self._genre_lines.get(genre)
        if ln:
            doc    = self._t.document()
            block  = doc.findBlockByNumber(ln - 1)
            self._t.setTextCursor(_QTC(block))
            self._t.ensureCursorVisible()

    # ── click handler ─────────────────────────────────────────────────────────

    def _click_at(self, line_no: int, col_no: int) -> None:
        if not self._focus:
            if line_no in self._sat_map:
                for cs, ce, genre, sub in self._sat_map[line_no]:
                    if cs <= col_no <= ce + 2:
                        self._zoom_in(genre, sub)
                        return
            for genre, (gr, gc) in self._pos.items():
                if self._genre_lines.get(genre) != line_no:
                    continue
                label_end = gc + 2 + len(genre) + 4 + len(
                    str(_leaf_count(self._tree[genre]))
                )
                if gc <= col_no <= label_end + 2:
                    if genre in self._graph_nodes:
                        self._graph_cursor_idx = self._graph_nodes.index(genre)
                    self._zoom_in(genre)
                    return
            return

        if line_no in self._line_paths:
            path = self._line_paths[line_no]
            self._cursor = path
            self._highlight(path)
            self._ctrl.on_play_path(path)  # type: ignore[union-attr]
            return

        for genre, ln in self._genre_lines.items():
            if ln == line_no:
                if self._focus and self._focus[0] == genre:
                    self._zoom_out()
                else:
                    self._zoom_in(genre)
                return

        for key, ln in self._sub_lines.items():
            if ln == line_no:
                genre, sub = key.split("\x00", 1)
                self._zoom_in(genre, sub)
                return

    # ── keyboard ──────────────────────────────────────────────────────────────

    def keyPressEvent(self, event) -> None:
        key = event.key()

        if key == Qt.Key.Key_I or key == Qt.Key.Key_Up:
            if not self._focus:
                self._move_graph_cursor(-1)
            else:
                self._move_cursor(-1)

        elif key == Qt.Key.Key_W or key == Qt.Key.Key_Down:
            if not self._focus:
                self._move_graph_cursor(+1)
            else:
                self._move_cursor(+1)

        elif key == Qt.Key.Key_A:
            if not self._focus:
                self._move_graph_cursor(+1)
            else:
                self._move_cursor(+1)

        elif key == Qt.Key.Key_L:
            if not self._focus:
                self._move_graph_cursor(-1)
            else:
                self._move_cursor(-1)

        elif key == Qt.Key.Key_D or key == Qt.Key.Key_Return:
            if not self._focus:
                if self._graph_nodes:
                    self._zoom_in(self._graph_nodes[self._graph_cursor_idx])
            elif self._cursor and self._cursor in self._path_lines:
                self._ctrl.on_play_path(self._cursor)  # type: ignore[union-attr]

        elif key == Qt.Key.Key_J:
            self._cursor = None
            self._t.setExtraSelections([])

        elif key == Qt.Key.Key_H or key == Qt.Key.Key_Right:
            if not self._focus:
                if self._graph_nodes:
                    self._zoom_in(self._graph_nodes[self._graph_cursor_idx])
            elif len(self._focus) == 1:
                genre    = self._focus[0]
                sub_tree = self._tree.get(genre, {})
                subs     = sorted(k for k in sub_tree if k is not None)
                if subs:
                    self._zoom_in(genre, subs[0])

        elif key in (Qt.Key.Key_F, Qt.Key.Key_Escape, Qt.Key.Key_Left):
            self._zoom_out()

        elif key == Qt.Key.Key_E:
            self._next_section()

        elif key == Qt.Key.Key_K:
            self._k_held = True

        elif key == Qt.Key.Key_S:
            if self._k_held:
                try:
                    tabs = self._ctrl.tabs  # type: ignore[union-attr]
                    tab_keys = [k for k, _ in tabs._TAB_KEYS]
                    idx = self._tab_widget.currentIndex() if hasattr(self, "_tab_widget") else 0
                    tabs.switch_to(tab_keys[(idx + 1) % len(tab_keys)])
                except Exception:
                    pass

        elif key == Qt.Key.Key_R:
            self.rebuild()

        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_K:
            self._k_held = False
        super().keyReleaseEvent(event)

    def _next_section(self) -> None:
        from PySide6.QtGui import QTextCursor as _QTC
        if not self._section_lines:
            return
        cursor  = self._t.textCursor()
        cur_ln  = cursor.blockNumber() + 1
        nxt     = next(
            (ln for ln in self._section_lines if ln > cur_ln),
            self._section_lines[0],
        )
        doc   = self._t.document()
        block = doc.findBlockByNumber(nxt - 1)
        self._t.setTextCursor(_QTC(block))
        self._t.ensureCursorVisible()
