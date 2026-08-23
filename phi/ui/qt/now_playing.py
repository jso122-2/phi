# -*- coding: utf-8 -*-
"""phi.ui.qt.now_playing — PySide6 full-spectrum ASCII album art panel.

Replaces phi.ui.now_playing.NowPlayingPanel.

The ASCII grid is computed entirely off the main thread (same prefeed_art /
commit_art pattern as the Tkinter version) and painted via QPainter in
paintEvent.  No HTML, no QTextEdit — pure painter path.

Public API (mirrors NowPlayingPanel)
--------------------------------------
    set_track(path, meta)
    set_title_only(path)
    set_art(art_bytes)
    prefeed_art(art_bytes, cols, rows, on_ready=None)
    commit_art()
    commit_art_or_wait(on_ready)
    reset()
    set_rating(stars)   # no-op
"""
from __future__ import annotations

import threading
from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QResizeEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

from phi.config import ACC2, BG
from phi.meta.art import art_to_ascii_colored, ascii_bake, ascii_load

_FONT_FAMILY = "Menlo"
_FONT_SIZE   = 4          # smaller → denser grid, more characters
_RESIZE_DELAY_MS = 60     # faster resize response

_PH_CHAR  = "φ"
_PH_COLOR = ACC2

_Grid = List[List[Tuple[str, str]]]


def _placeholder_grid(cols: int, rows: int) -> _Grid:
    mid_r = rows // 2
    mid_c = max(0, cols // 2 - 1)
    grid: _Grid = []
    for r in range(rows):
        if r == mid_r:
            row: List[Tuple[str, str]] = [(" ", _PH_COLOR)] * cols
            if mid_c < cols:
                row = list(row)
                row[mid_c] = (_PH_CHAR, _PH_COLOR)
        else:
            row = [(" ", _PH_COLOR)] * cols
        grid.append(row)
    return grid


class NowPlayingWidget(QWidget):
    """
    Full-spectrum coloured ASCII art panel.

    Paints the grid directly via QPainter — zero widget-churn, no HTML.

    CAIRRN prefeed pattern preserved: prefeed_art() runs PIL off-thread;
    commit_art() paints the stored grid on the main thread.
    """

    def __init__(self, schedule: Optional[Callable] = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._schedule     = schedule
        self._art_bytes: Optional[bytes] = None
        self._grid: _Grid  = []
        self._cols         = 64
        self._rows         = 32
        self._char_w       = 4.0
        self._char_h       = 8.0

        self._pending_grid: Optional[_Grid] = None
        self._on_ready_cb: Optional[Callable] = None
        self._prefeed_lock = threading.Lock()

        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._render)

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        font = QFont(_FONT_FAMILY, _FONT_SIZE)
        fm = QFontMetrics(font)
        self._char_w = max(1.0, fm.averageCharWidth())
        self._char_h = max(1.0, float(fm.height()))

        self._grid = _placeholder_grid(self._cols, self._rows)

    # ── Qt painting ────────────────────────────────────────────────────────────

    def paintEvent(self, _event: object) -> None:
        if not self._grid:
            return
        rows = len(self._grid)
        cols = len(self._grid[0]) if rows else 0
        if not rows or not cols:
            return

        w = self.width()
        h = self.height()

        # Stretch each cell to fill the widget exactly — no side bars, no scan lines.
        cw = w / cols
        ch = h / rows

        painter = QPainter(self)
        painter.setFont(QFont(_FONT_FAMILY, _FONT_SIZE))
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, False)

        # Full-widget background so nothing leaks through.
        painter.fillRect(0, 0, w, h, QColor(BG))

        for r_idx, row in enumerate(self._grid):
            y_top  = int(r_idx * ch)
            cell_h = max(1, int((r_idx + 1) * ch) - y_top)
            for c_idx, (char, color) in enumerate(row):
                x_left = int(c_idx * cw)
                cell_w = max(1, int((c_idx + 1) * cw) - x_left)
                cell   = QRect(x_left, y_top, cell_w, cell_h)

                # Dark tint fill eliminates any gap between rows/cols.
                painter.fillRect(cell, QColor(color).darker(320))

                # Character in full pixel colour — classic coloured ASCII look.
                painter.setPen(QColor(color))
                painter.drawText(
                    cell,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                    char,
                )

        painter.end()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        w = event.size().width()
        h = event.size().height()
        if w < 10 or h < 10:
            return
        # Round up so the grid always covers every pixel even at fractional sizes.
        new_cols = max(8,  -(-w // max(1, int(self._char_w))))   # ceil division
        new_rows = max(4,  -(-h // max(1, int(self._char_h))))
        if new_cols == self._cols and new_rows == self._rows:
            return
        self._cols = new_cols
        self._rows = new_rows
        self._resize_timer.start(_RESIZE_DELAY_MS)

    def sizeHint(self) -> QSize:
        return QSize(520, 420)

    # ── public API ─────────────────────────────────────────────────────────────

    def set_track(self, path: str, meta: dict | None) -> None:  # noqa: ARG002
        self.set_art(meta.get("art_bytes") if meta else None)

    def set_title_only(self, path: str) -> None:  # noqa: ARG002
        self._art_bytes = None
        self._set_grid(_placeholder_grid(self._cols, self._rows))

    def set_art(self, art_bytes: bytes | None) -> None:
        self._art_bytes = art_bytes
        if not art_bytes:
            self._set_grid(_placeholder_grid(self._cols, self._rows))
            return
        _post = self._schedule if self._schedule else (lambda ms, fn: QTimer.singleShot(ms, fn))
        # Always render at current widget resolution for full-fidelity fill.
        # The bake path runs in parallel so subsequent opens are instant.
        self.prefeed_art(
            art_bytes,
            self._cols,
            self._rows,
            on_ready=lambda: _post(0, self.commit_art),
        )
        threading.Thread(target=ascii_bake, args=(art_bytes,), daemon=True).start()

    def set_rating(self, stars: int) -> None:  # noqa: ARG002
        pass

    def prefeed_art(
        self,
        art_bytes: bytes,
        cols: int,
        rows: int,
        on_ready: Optional[Callable] = None,
    ) -> None:
        """Compute the ASCII grid off the main thread.  Safe to call from any thread."""
        with self._prefeed_lock:
            self._pending_grid = None
            if on_ready is not None:
                self._on_ready_cb = on_ready

        def _run() -> None:
            grid = art_to_ascii_colored(art_bytes, cols, rows)
            cb: Optional[Callable] = None
            if grid:
                with self._prefeed_lock:
                    self._pending_grid = grid
                    cb = self._on_ready_cb
                    self._on_ready_cb = None
            if cb is not None:
                try:
                    cb()
                except Exception:
                    pass

        threading.Thread(target=_run, daemon=True).start()

    def commit_art(self) -> None:
        """Paint pending pre-computed grid.  MAIN THREAD ONLY."""
        with self._prefeed_lock:
            grid = self._pending_grid
            self._pending_grid = None
        if grid is not None:
            self._set_grid(grid)

    def commit_art_or_wait(self, on_ready: Callable) -> None:
        """Paint immediately if PIL done; otherwise arm the callback.  MAIN THREAD ONLY."""
        with self._prefeed_lock:
            grid = self._pending_grid
            if grid is not None:
                self._pending_grid = None
            else:
                self._on_ready_cb = on_ready
        if grid is not None:
            self._set_grid(grid)

    def reset(self) -> None:
        with self._prefeed_lock:
            self._pending_grid = None
            self._on_ready_cb  = None
        self._art_bytes = None
        self._set_grid(_placeholder_grid(self._cols, self._rows))

    # ── internal ───────────────────────────────────────────────────────────────

    def _set_grid(self, grid: _Grid) -> None:
        self._grid = grid
        self.update()

    def _render(self) -> None:
        if self._art_bytes:
            grid = ascii_load(self._art_bytes)
            if grid is not None:
                self._set_grid(grid)
                return
            _post = self._schedule if self._schedule else (lambda ms, fn: QTimer.singleShot(ms, fn))
            self.prefeed_art(
                self._art_bytes,
                self._cols,
                self._rows,
                on_ready=lambda: _post(0, self.commit_art),
            )
        else:
            self._set_grid(_placeholder_grid(self._cols, self._rows))
