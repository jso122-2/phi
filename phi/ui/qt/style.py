# -*- coding: utf-8 -*-
"""phi.ui.qt.style — Qt stylesheet built from the existing phi palette.

Single source of truth: phi.ui.style (unchanged).
This module converts those hex constants into a QSS stylesheet and exposes
apply(QApplication) as the one call site in PhiMainWindow.__init__.
"""
from __future__ import annotations

from phi.ui.style import (
    BG, CARD, CARD2, BORDER,
    ACC, ACC2, GOLD,
    FG, MUTED,
    ENTRY_BG, ENTRY_FG,
)


STYLESHEET: str = f"""
/* ── Base ──────────────────────────────────────────────────────────────── */
QWidget {{
    background-color: {BG};
    color: {FG};
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 11px;
}}

QMainWindow {{
    background-color: {BG};
}}

/* ── Labels ─────────────────────────────────────────────────────────────── */
QLabel {{
    background: transparent;
    color: {FG};
}}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
QPushButton {{
    background: transparent;
    color: {MUTED};
    border: none;
    padding: 4px 8px;
    font-size: 11px;
}}
QPushButton:hover  {{ color: {FG}; }}
QPushButton:pressed {{ color: {ACC}; }}
QPushButton[active="true"] {{ color: {ACC}; }}

/* ── Line edit / search ──────────────────────────────────────────────────── */
QLineEdit {{
    background-color: {ENTRY_BG};
    color: {ENTRY_FG};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 3px 6px;
    selection-background-color: {ACC2};
    selection-color: {FG};
}}
QLineEdit:focus {{ border-color: {ACC}; }}

/* ── List / tree ─────────────────────────────────────────────────────────── */
QListWidget, QListView, QTreeView {{
    background-color: {CARD};
    color: {FG};
    border: none;
    outline: none;
    alternate-background-color: {CARD2};
}}
QListWidget::item, QListView::item, QTreeView::item {{
    padding: 3px 6px;
    border: none;
}}
QListWidget::item:selected, QListView::item:selected, QTreeView::item:selected {{
    background-color: {ACC2};
    color: {FG};
}}
QListWidget::item:hover, QListView::item:hover {{
    background-color: {CARD2};
}}

/* ── Scroll bars ─────────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {CARD2};
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    min-height: 24px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {CARD2};
    height: 6px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    min-width: 24px;
    border-radius: 3px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Sliders (seek + volume) ─────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    height: 3px;
    background: {CARD2};
    border-radius: 1px;
}}
QSlider::handle:horizontal {{
    width: 12px;
    height: 12px;
    margin: -5px 0;
    border-radius: 6px;
    background: {FG};
}}
QSlider::handle:horizontal:hover {{ background: {ACC}; }}
QSlider::sub-page:horizontal {{ background: {ACC}; border-radius: 1px; }}

/* ── Dialogs ─────────────────────────────────────────────────────────────── */
QDialog {{
    background-color: {CARD};
    border: 1px solid {ACC};
}}

/* ── Text / read-only views ──────────────────────────────────────────────── */
QTextEdit, QTextBrowser, QPlainTextEdit {{
    background-color: {BG};
    color: {FG};
    border: none;
    selection-background-color: {CARD2};
    selection-color: {FG};
}}

/* ── Splitter ────────────────────────────────────────────────────────────── */
QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical   {{ height: 1px; }}

/* ── Stack / frame ───────────────────────────────────────────────────────── */
QFrame[role="card"] {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}
"""


def apply(app: object) -> None:
    """Apply the phi dark stylesheet to a QApplication instance."""
    app.setStyleSheet(STYLESHEET)  # type: ignore[attr-defined]
