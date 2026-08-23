# -*- coding: utf-8 -*-
"""phi.ui.qt.overlay — PySide6 ⌘K command palette.

Replaces phi.ui.overlay.CommandOverlay.

Built once, shown/hidden via show()/hide().  Async recent-track fetch keeps
the window responsive (same pattern as the Tk version we already hardened).

Public API (mirrors CommandOverlay)
--------------------------------------
    show()
    hide()
"""
from __future__ import annotations

import os
import threading
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from phi.config import ACC, ACC2, BG, CARD, CARD2, FG, MUTED

_MAX_RESULTS = 12
_HINT        = "type to search or ↑↓ to browse recent tracks"


class CommandOverlay(QDialog):
    """Floating ⌘K palette.

    Appears centred over the parent window, dismisses on Escape or focus loss.
    """

    def __init__(self, parent: Any, ctrl: Any) -> None:
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self._ctrl    = ctrl
        self._results: list[dict] = []
        self._sel_idx = 0
        self.setStyleSheet(
            f"background: {CARD}; border: 1px solid {ACC}; border-radius: 6px;"
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._build()

    # ── build ──────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        # ── search row ────────────────────────────────────────────────────────
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        cmd_lbl = QLabel("⌘K")
        cmd_lbl.setStyleSheet(f"color: {ACC}; font-size: 13px; font-weight: bold;")
        cmd_lbl.setFixedWidth(32)

        self._entry = QLineEdit()
        self._entry.setPlaceholderText(_HINT)
        self._entry.setStyleSheet(
            f"background: {CARD2}; color: {FG}; border: 1px solid {ACC2}; "
            f"border-radius: 4px; padding: 6px 10px; font-size: 13px;"
        )
        self._entry.textChanged.connect(self._on_text_changed)

        search_row.addWidget(cmd_lbl)
        search_row.addWidget(self._entry, stretch=1)
        root.addLayout(search_row)

        # ── results list ─────────────────────────────────────────────────────
        self._list = QListWidget()
        self._list.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: none; outline: none;"
            f"QListWidget::item {{ padding: 4px 8px; }}"
            f"QListWidget::item:selected {{ background: {ACC2}; }}"
        )
        self._list.setMaximumHeight(320)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list.itemDoubleClicked.connect(self._activate_current)
        root.addWidget(self._list)

        # ── hint label ────────────────────────────────────────────────────────
        self._hint_lbl = QLabel(_HINT)
        self._hint_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
        self._hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._hint_lbl)

    # ── public API ─────────────────────────────────────────────────────────────

    def show(self) -> None:
        self._entry.clear()
        self._hint_lbl.setText(_HINT)
        self._results = []
        self._sel_idx = 0
        self._render_results()
        self._reposition()
        super().show()
        self.raise_()
        self._entry.setFocus()
        QTimer.singleShot(0, self._fetch_recent_async)

    def hide(self) -> None:
        super().hide()

    # ── keyboard handling ──────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.hide()
            return
        if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self._activate_current()
            return
        if key == Qt.Key.Key_Up:
            self._sel_idx = max(0, self._sel_idx - 1)
            self._list.setCurrentRow(self._sel_idx)
            return
        if key == Qt.Key.Key_Down:
            self._sel_idx = min(len(self._results) - 1, self._sel_idx + 1)
            self._list.setCurrentRow(self._sel_idx)
            return
        super().keyPressEvent(event)

    # ── results ────────────────────────────────────────────────────────────────

    def _on_text_changed(self, text: str) -> None:
        if not text.strip():
            self._fetch_recent_async()
            return
        self._search(text.strip())

    def _search(self, query: str) -> None:
        try:
            lib     = self._ctrl.library
            results = []
            q_low   = query.lower()
            for path in lib.playlist:
                meta  = lib.get_meta(path) or {}
                title  = meta.get("title")  or os.path.basename(path)
                artist = meta.get("artist") or ""
                if q_low in title.lower() or q_low in artist.lower():
                    results.append({
                        "path":   path,
                        "title":  title,
                        "artist": artist,
                        "plays":  (lib.play_stats.get(path) or {}).get("plays", 0),
                    })
                    if len(results) >= _MAX_RESULTS:
                        break
        except Exception:
            results = []
        self._set_results(results)

    def _fetch_recent_async(self) -> None:
        def _work() -> None:
            try:
                lib    = self._ctrl.library
                stats  = lib.play_stats
                ranked: list[tuple] = []
                for path, s in stats.items():
                    lp = s.get("last_played") or ""
                    if lp:
                        meta = lib.get_meta(path) or {}
                        ranked.append((lp, path, meta, s))
                ranked.sort(key=lambda x: x[0], reverse=True)
                results = []
                for _, path, meta, s in ranked[:_MAX_RESULTS]:
                    results.append({
                        "path":   path,
                        "title":  meta.get("title")  or os.path.basename(path),
                        "artist": meta.get("artist") or "",
                        "plays":  s.get("plays", 0),
                    })
            except Exception:
                results = []
            if self.isVisible():
                QTimer.singleShot(0, lambda: self._set_results(results))

        threading.Thread(target=_work, daemon=True).start()

    def _set_results(self, results: list[dict]) -> None:
        self._results = results
        self._sel_idx = 0
        self._render_results()

    def _render_results(self) -> None:
        self._list.clear()
        for r in self._results:
            artist = r.get("artist", "")
            plays  = r.get("plays", 0)
            line   = r["title"]
            if artist:
                line += f"  —  {artist}"
            if plays:
                line += f"  ▶{plays}"
            item = QListWidgetItem(line)
            item.setForeground(QColor(FG))
            self._list.addItem(item)
        if self._results:
            self._list.setCurrentRow(0)
            hint = f"{len(self._results)} result{'s' if len(self._results) != 1 else ''}"
        else:
            hint = _HINT
        self._hint_lbl.setText(hint)

    def _activate_current(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._results):
            path = self._results[row]["path"]
            self._ctrl.on_play_path(path)
            self.hide()

    # ── positioning ────────────────────────────────────────────────────────────

    def _reposition(self) -> None:
        if self.parent() and self.parent().isVisible():
            parent_geo = self.parent().geometry()
            pw = parent_geo.width()
            px = parent_geo.x()
            py = parent_geo.y()
            dw = self.sizeHint().width()
            self.move(px + (pw - dw) // 2, py + 80)
        else:
            self.move(200, 80)
