# -*- coding: utf-8 -*-
"""phi.ui.qt.jim_help — PySide6 Jim-bindings help overlay.

Replaces phi.ui.jim_help.JimHelpOverlay (tk.Toplevel).

Public API (mirrors JimHelpOverlay)
--------------------------------------
    show()
    hide()
    toggle()
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from phi.config import ACC, ACC2, BG, CARD, CARD2, FG, MUTED
from phi.ui.qt.keys import JIM_BINDING_TABLE


class JimHelpOverlay:
    """
    Floating Jim-bindings reference panel.

    Built once and reused (show/hide).  Centred over the parent window.
    Dismiss with  g · Esc.
    """

    def __init__(self, parent: QWidget) -> None:
        self._parent = parent
        self._dlg: _HelpDialog | None = None

    # ── public ────────────────────────────────────────────────────────────────

    def show(self) -> None:
        if self._dlg is None:
            self._dlg = _HelpDialog(self._parent)
        self._dlg.show()
        self._dlg.raise_()
        self._dlg.activateWindow()

    def hide(self) -> None:
        if self._dlg:
            self._dlg.hide()

    def toggle(self) -> None:
        if self._dlg and self._dlg.isVisible():
            self.hide()
        else:
            self.show()


class _HelpDialog(QDialog):
    """The actual dialog window — built once and toggled."""

    WIDTH  = 480
    HEIGHT = 520

    def __init__(self, parent: QWidget) -> None:
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool,
        )
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setStyleSheet(
            f"QDialog {{ background: {CARD}; border: 1px solid {ACC}; }}"
        )
        self.resize(self.WIDTH, self.HEIGHT)
        self._build()
        self._center_on_parent()

    def _center_on_parent(self) -> None:
        if self.parent():
            pg = self.parent().frameGeometry()  # type: ignore[union-attr]
            cx = pg.center()
            self.move(cx.x() - self.WIDTH // 2, cx.y() - self.HEIGHT // 2)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── header ────────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setStyleSheet(f"background: {CARD2};")
        hdr_row = QHBoxLayout(hdr)
        hdr_row.setContentsMargins(12, 7, 12, 7)

        title = QLabel("  φ  jim bindings")
        title.setStyleSheet(
            f"color: {FG}; font-family: Menlo, monospace; font-size: 11px; font-weight: bold;"
        )
        hint = QLabel("g · Esc  to close")
        hint.setStyleSheet(f"color: {MUTED}; font-family: Menlo, monospace; font-size: 9px;")

        hdr_row.addWidget(title)
        hdr_row.addStretch()
        hdr_row.addWidget(hint)
        root.addWidget(hdr)

        # ── scrollable binding table ──────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {CARD}; border: none; }}"
            f"QScrollBar:vertical {{ background: {CARD}; width: 4px; }}"
            f"QScrollBar::handle:vertical {{ background: {CARD2}; border-radius: 2px; }}"
        )

        body   = QWidget()
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(18, 8, 18, 8)
        body_l.setSpacing(1)

        section = None
        for sec, key, desc in JIM_BINDING_TABLE:
            if sec != section:
                section = sec
                if body_l.count() > 0:
                    spacer = QLabel("")
                    spacer.setFixedHeight(6)
                    body_l.addWidget(spacer)
                sec_lbl = QLabel(sec.upper())
                sec_lbl.setStyleSheet(
                    f"color: {ACC}; font-family: Menlo, monospace; "
                    f"font-size: 8px; font-weight: bold; padding-top: 4px;"
                )
                body_l.addWidget(sec_lbl)

            row_w  = QWidget()
            row_l  = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(16)

            key_lbl = QLabel(f"  {key}")
            key_lbl.setFixedWidth(110)
            key_lbl.setStyleSheet(
                f"color: {FG}; font-family: Menlo, monospace; font-size: 10px;"
            )
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet(
                f"color: {MUTED}; font-family: Menlo, monospace; font-size: 10px;"
            )

            row_l.addWidget(key_lbl)
            row_l.addWidget(desc_lbl)
            row_l.addStretch()
            body_l.addWidget(row_w)

        body_l.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        # ── footer ────────────────────────────────────────────────────────────
        ftr = QWidget()
        ftr.setStyleSheet(f"background: {CARD2};")
        ftr_row = QHBoxLayout(ftr)
        ftr_row.setContentsMargins(12, 4, 12, 4)
        ftr_lbl = QLabel("  bindings live in  ~/.phi/jim_bindings.json")
        ftr_lbl.setStyleSheet(
            f"color: {MUTED}; font-family: Menlo, monospace; font-size: 8px;"
        )
        ftr_row.addWidget(ftr_lbl)
        root.addWidget(ftr)

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() in (Qt.Key.Key_Escape, Qt.Key.Key_G):
            self.hide()
        else:
            super().keyPressEvent(e)
