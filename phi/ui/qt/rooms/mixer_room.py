# -*- coding: utf-8 -*-
"""phi.ui.qt.rooms.mixer_room — Qt BPM / key compatibility mixer.

Replaces phi.ui.rooms.mixer_room.MixerRoom (tk.Frame + tk.Canvas).

Shows the library as a grid of cells coloured by BPM range x Camelot key.
Below the grid, the current queue is shown as a chain of transitions with
compatibility indicators.

Room protocol: on_show(), on_refresh(), sync_transport()
"""
from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from phi.config import ACC, ACC2, BG, CARD, CARD2, FG, METER_CRIT, METER_OK, METER_WARN, MUTED
from phi.ui.qt.rooms._mini_transport import MiniTransportWidget

# BPM bands
_BPM_BANDS = [
    ("<80",    0,   80),
    ("80",    80,  100),
    ("100",  100,  120),
    ("120",  120,  140),
    ("140+", 140, 9999),
]

# Camelot 24 slots (1A..12B)
_CAMELOT_COLS = [f"{n}{ab}" for n in range(1, 13) for ab in ("A", "B")]


def _camelot_dist(a: str, b: str) -> int:
    if not a or not b:
        return 3
    try:
        an, al = int(a[:-1]), a[-1]
        bn, bl = int(b[:-1]), b[-1]
    except (ValueError, IndexError):
        return 3
    num_dist = min(abs(an - bn), 12 - abs(an - bn))
    if an == bn and al == bl:
        return 0
    if num_dist == 0:
        return 1
    if num_dist == 1 and al == bl:
        return 1
    if num_dist <= 2:
        return 2
    return 3


def _compat_color(bpm_a: float, key_a: str, bpm_b: float, key_b: str) -> str:
    if bpm_a > 0 and bpm_b > 0:
        delta = abs(bpm_a - bpm_b) / max(bpm_a, bpm_b)
    else:
        delta = 0.0
    key_d = _camelot_dist(key_a, key_b)
    if key_d <= 1 and delta <= 0.08:
        return METER_OK
    if key_d <= 2 and delta <= 0.15:
        return METER_WARN
    return METER_CRIT


def _bpm_band(bpm: float) -> int:
    for i, (_, lo, hi) in enumerate(_BPM_BANDS):
        if lo <= bpm < hi:
            return i
    return len(_BPM_BANDS) - 1


class MixerRoom(QWidget):
    """BPM / key compatibility mixer page."""

    def __init__(self, parent: QWidget | None = None, ctrl: object = None) -> None:
        super().__init__(parent)
        self._ctrl       = ctrl
        self._cache_warm = False
        self._grid_data: dict[tuple[int, int], list[str]] = {}
        self._build()

    # ── layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setStyleSheet(f"background: {CARD2};")
        hdr_row = QHBoxLayout(hdr)
        hdr_row.setContentsMargins(16, 8, 16, 8)

        title = QLabel("Mixer")
        title.setStyleSheet(f"color: {ACC}; font-size: 13px; font-weight: bold;")
        sub   = QLabel("BPM × Camelot key compatibility grid")
        sub.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
        refresh_btn = QPushButton("refresh")
        refresh_btn.setStyleSheet(
            f"color: {MUTED}; background: transparent; border: none; font-size: 9px;"
        )
        refresh_btn.clicked.connect(self.on_refresh)

        hdr_row.addWidget(title)
        hdr_row.addWidget(sub)
        hdr_row.addStretch()
        hdr_row.addWidget(refresh_btn)
        root.addWidget(hdr)

        # BPM × Camelot grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"background: {BG}; border: none;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        grid_container = QWidget()
        grid_layout    = QVBoxLayout(grid_container)
        grid_layout.setContentsMargins(16, 12, 16, 8)
        grid_layout.setSpacing(4)

        self._grid_table = QTableWidget(len(_BPM_BANDS), len(_CAMELOT_COLS))
        self._grid_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._grid_table.setHorizontalHeaderLabels(_CAMELOT_COLS)
        self._grid_table.setVerticalHeaderLabels([b[0] for b in _BPM_BANDS])
        self._grid_table.horizontalHeader().setDefaultSectionSize(32)
        self._grid_table.verticalHeader().setDefaultSectionSize(26)
        self._grid_table.setStyleSheet(
            f"QTableWidget {{ background: {BG}; color: {FG}; "
            f"gridline-color: {CARD2}; border: none; font-size: 8px; }}"
            f"QHeaderView::section {{ background: {CARD2}; color: {MUTED}; "
            f"font-size: 7px; border: none; padding: 2px; }}"
        )
        self._grid_table.setFixedHeight(len(_BPM_BANDS) * 26 + 30)
        self._grid_table.cellClicked.connect(self._on_cell_click)
        grid_layout.addWidget(self._grid_table)

        # Chain strip label
        chain_lbl = QLabel("Queue transitions")
        chain_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
        grid_layout.addWidget(chain_lbl)

        self._chain_list = QListWidget()
        self._chain_list.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: none; font-size: 9px;"
        )
        self._chain_list.setMaximumHeight(120)
        grid_layout.addWidget(self._chain_list)
        grid_layout.addStretch()

        scroll.setWidget(grid_container)
        root.addWidget(scroll, stretch=1)

        self._mini = MiniTransportWidget(ctrl=self._ctrl)
        root.addWidget(self._mini)

    # ── room protocol ─────────────────────────────────────────────────────────

    def on_show(self) -> None:
        if not self._cache_warm:
            QTimer.singleShot(0, self.on_refresh)

    def on_refresh(self) -> None:
        self._build_grid()
        self._build_chain()
        self._cache_warm = True

    def sync_transport(
        self,
        title: str,
        artist: str,
        playing: bool,
        pos: float,
        duration: float,
    ) -> None:
        self._mini.sync(title, artist, playing, pos, duration)

    def mark_playing(self, path: str | None) -> None:
        pass

    # ── grid ──────────────────────────────────────────────────────────────────

    def _build_grid(self) -> None:
        lib  = self._ctrl.library  # type: ignore[union-attr]
        grid: dict[tuple[int, int], list[str]] = {}

        for path in lib.playlist:
            ann = lib.get_annotation(path) or {}
            bpm_raw = ann.get("bpm", 0)
            try:
                bpm = float(bpm_raw) if bpm_raw else 0.0
            except (TypeError, ValueError):
                bpm = 0.0
            key = str(ann.get("camelot_key") or "").strip()
            if not key or key not in _CAMELOT_COLS:
                continue
            band = _bpm_band(bpm)
            col  = _CAMELOT_COLS.index(key)
            grid.setdefault((band, col), []).append(path)

        self._grid_data = grid

        for r in range(len(_BPM_BANDS)):
            for c in range(len(_CAMELOT_COLS)):
                paths = grid.get((r, c), [])
                n     = len(paths)
                item  = QTableWidgetItem(str(n) if n else "")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if n > 0:
                    intensity = min(255, 60 + n * 18)
                    item.setBackground(QColor(0, intensity // 2, intensity // 3))
                    item.setForeground(QColor("#ffffff"))
                self._grid_table.setItem(r, c, item)

    def _on_cell_click(self, row: int, col: int) -> None:
        paths = self._grid_data.get((row, col), [])
        if not paths:
            return
        lib = self._ctrl.library  # type: ignore[union-attr]
        dlg = QDialog(self)
        dlg.setWindowTitle(
            f"BPM {_BPM_BANDS[row][0]}  ·  {_CAMELOT_COLS[col]}"
        )
        dlg.resize(400, 300)
        v = QVBoxLayout(dlg)
        lst = QListWidget()
        lst.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: none; font-size: 9px;"
        )
        for p in paths:
            m = lib.get_meta(p) or {}
            lst.addItem(m.get("title") or os.path.basename(p))
        lst.itemDoubleClicked.connect(
            lambda item, ps=paths: (
                self._ctrl.on_play_path(ps[lst.row(item)]),  # type: ignore[union-attr]
                dlg.accept(),
            )
        )
        v.addWidget(lst)
        dlg.exec()

    # ── chain strip ───────────────────────────────────────────────────────────

    def _build_chain(self) -> None:
        self._chain_list.clear()
        lib   = self._ctrl.library  # type: ignore[union-attr]
        queue = list(self._ctrl.queue.queue)  # type: ignore[union-attr]
        if len(queue) < 2:
            return

        prev_path = queue[0]
        for path in queue[1:6]:
            pa = lib.get_annotation(prev_path) or {}
            ca = lib.get_annotation(path) or {}
            try:
                bpm_a = float(pa.get("bpm") or 0)
                bpm_b = float(ca.get("bpm") or 0)
            except (TypeError, ValueError):
                bpm_a = bpm_b = 0.0
            key_a = str(pa.get("camelot_key") or "")
            key_b = str(ca.get("camelot_key") or "")

            compat = _compat_color(bpm_a, key_a, bpm_b, key_b)
            ma = lib.get_meta(prev_path) or {}
            mb = lib.get_meta(path)      or {}
            ta = ma.get("title") or os.path.basename(prev_path)
            tb = mb.get("title") or os.path.basename(path)

            text = f"{ta[:20]}  →  {tb[:20]}"
            item = QListWidgetItem(text)
            item.setForeground(QColor(compat))
            self._chain_list.addItem(item)
            prev_path = path
