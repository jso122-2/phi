# -*- coding: utf-8 -*-
"""phi.ui.qt.rooms._dragon_panel — Dragon Curve info panel widget.

Exports:
    DragonInfoPanel — right-side panel: D4 scores, fold bits, segment info,
                      anchor / walk / arc controls.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from phi.config import (
    ACC, ACC2, BORDER, CARD, CARD2,
    FG, INDIGO, MUTED, METER_OK,
)
from phi.ui.qt.rooms._dragon_canvas import _GaugeBar


class DragonInfoPanel(QWidget):
    """
    Right-side panel: live D4 scores, fold bits, segment info, anchor button.

    Two display modes for scores:
        normal  — ACC colour, full opacity (committed click or playback)
        preview — MUTED colour, lower opacity (hover ghost)
    """

    anchor_requested  = Signal()
    walk_requested    = Signal()
    arc_shape_changed = Signal(str)
    arc_mode_toggled  = Signal()

    _W = 230

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(self._W)
        self.setStyleSheet(f"background: {CARD}; border-left: 1px solid {BORDER};")
        self._build()
        self._anchored = False

    # ── layout helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _sep(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {ACC}; font-size: 8px; letter-spacing: 2px; "
            f"border: none; background: transparent;"
        )
        return lbl

    @staticmethod
    def _val_lbl(text: str = "—") -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {FG}; font-size: 10px; font-family: Menlo, monospace; "
            f"border: none; background: transparent;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return lbl

    @staticmethod
    def _key_lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; border: none; background: transparent;"
        )
        return lbl

    def _kv(self, root: QVBoxLayout, key: str) -> QLabel:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(self._key_lbl(key))
        v = self._val_lbl()
        row.addWidget(v, stretch=1)
        root.addLayout(row)
        return v

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 16, 14, 12)
        root.setSpacing(4)

        root.addWidget(self._sep("SCORES"))

        row_a = QHBoxLayout()
        row_a.setContentsMargins(0, 0, 0, 0)
        row_a.setSpacing(4)
        row_a.addWidget(self._key_lbl("D4_A"))
        self._d4a_val = self._val_lbl()
        row_a.addWidget(self._d4a_val, stretch=1)
        root.addLayout(row_a)

        self._d4a_gauge = _GaugeBar(ACC, parent=self)
        root.addWidget(self._d4a_gauge)

        root.addSpacing(2)
        self._d4b_val = self._kv(root, "D4_B")

        root.addSpacing(10)
        root.addWidget(self._sep("FOLD BITS"))
        bits_row = QHBoxLayout()
        bits_row.setContentsMargins(0, 0, 0, 0)
        bits_row.setSpacing(3)
        self._bit_cells: list[QLabel] = []
        for _ in range(8):
            cell = QLabel("□")
            cell.setFixedWidth(18)
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.setStyleSheet(
                f"color: {MUTED}; font-size: 12px; font-family: Menlo, monospace; "
                f"border: none; background: transparent;"
            )
            self._bit_cells.append(cell)
            bits_row.addWidget(cell)
        bits_row.addStretch()
        root.addLayout(bits_row)

        root.addSpacing(10)
        root.addWidget(self._sep("SEGMENT"))
        self._seg_val = self._kv(root, "index")
        self._t_val   = self._kv(root, "t")
        self._d1_val  = self._kv(root, "D1")
        self._d3_val  = self._kv(root, "D3")

        root.addSpacing(10)
        root.addWidget(self._sep("TRACK"))

        self._track_lbl = QLabel("♪  no track")
        self._track_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; word-wrap: true; "
            f"border: none; background: transparent;"
        )
        self._track_lbl.setWordWrap(True)
        root.addWidget(self._track_lbl)

        root.addSpacing(6)

        self._anchor_btn = QPushButton("Anchor Track")
        self._anchor_btn.setEnabled(False)
        self._anchor_btn.setStyleSheet(
            f"QPushButton {{"
            f"  color: {MUTED}; font-size: 9px; letter-spacing: 1px;"
            f"  background: {CARD2}; border: 1px solid {BORDER};"
            f"  padding: 4px 10px; border-radius: 3px;"
            f"}}"
            f"QPushButton:enabled {{"
            f"  color: {FG}; border-color: {ACC2};"
            f"}}"
            f"QPushButton:enabled:hover {{"
            f"  background: {ACC2}; color: {FG}; border-color: {ACC};"
            f"}}"
        )
        self._anchor_btn.clicked.connect(self.anchor_requested)
        root.addWidget(self._anchor_btn)

        self._anchor_status = QLabel("")
        self._anchor_status.setStyleSheet(
            f"color: {METER_OK}; font-size: 8px; font-family: Menlo, monospace; "
            f"border: none; background: transparent;"
        )
        root.addWidget(self._anchor_status)

        root.addSpacing(12)
        root.addWidget(self._sep("QUEUE"))
        root.addSpacing(4)

        self._walk_btn = QPushButton("↺  Walk Curve")
        self._walk_btn.setStyleSheet(
            f"QPushButton {{"
            f"  color: {FG}; font-size: 9px; letter-spacing: 1px;"
            f"  background: {CARD2}; border: 1px solid {INDIGO};"
            f"  padding: 4px 10px; border-radius: 3px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {INDIGO}; color: {FG}; border-color: {ACC};"
            f"}}"
            f"QPushButton[active=true] {{"
            f"  background: {INDIGO}; color: {ACC}; border-color: {ACC};"
            f"}}"
        )
        self._walk_btn.setProperty("active", False)
        self._walk_btn.clicked.connect(self.walk_requested)
        root.addWidget(self._walk_btn)

        root.addSpacing(12)
        root.addWidget(self._sep("SESSION ARC"))
        root.addSpacing(4)

        _arc_shapes = [
            ("FLAT",    "━━  Flat"),
            ("RISING",  "↗  Rise"),
            ("PEAK",    "▲  Peak"),
            ("WAVE",    "∿  Wave"),
        ]
        _btn_style_base = (
            f"QPushButton {{"
            f"  color: {MUTED}; font-size: 8px; letter-spacing: 1px;"
            f"  background: {CARD2}; border: 1px solid {BORDER};"
            f"  padding: 3px 0px; border-radius: 3px;"
            f"}}"
            f"QPushButton:checked {{"
            f"  color: {ACC}; background: {INDIGO}; border-color: {ACC};"
            f"}}"
            f"QPushButton:hover:!checked {{"
            f"  border-color: {INDIGO};"
            f"}}"
        )

        self._arc_shape_btns: dict[str, QPushButton] = {}
        self._arc_btn_group = QButtonGroup(self)
        self._arc_btn_group.setExclusive(True)
        for row_i in range(0, len(_arc_shapes), 2):
            row_w = QWidget(); row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0); row_l.setSpacing(4)
            for key, label in _arc_shapes[row_i : row_i + 2]:
                btn = QPushButton(label)
                btn.setCheckable(True)
                btn.setStyleSheet(_btn_style_base)
                btn.setFixedHeight(20)
                self._arc_btn_group.addButton(btn)
                self._arc_shape_btns[key] = btn
                btn.clicked.connect(lambda _checked, k=key: self.arc_shape_changed.emit(k))
                row_l.addWidget(btn)
            root.addWidget(row_w)

        self._arc_shape_btns["FLAT"].setChecked(True)

        root.addSpacing(4)
        self._arc_toggle_btn = QPushButton("Arc: OFF")
        self._arc_toggle_btn.setCheckable(True)
        self._arc_toggle_btn.setChecked(False)
        self._arc_toggle_btn.setStyleSheet(
            f"QPushButton {{"
            f"  color: {MUTED}; font-size: 9px; letter-spacing: 1px;"
            f"  background: {CARD2}; border: 1px solid {BORDER};"
            f"  padding: 4px 10px; border-radius: 3px;"
            f"}}"
            f"QPushButton:checked {{"
            f"  color: {ACC}; background: {INDIGO}; border-color: {ACC};"
            f"}}"
        )
        self._arc_toggle_btn.clicked.connect(self.arc_mode_toggled)
        root.addWidget(self._arc_toggle_btn)

        root.addStretch()

    # ── public update API ─────────────────────────────────────────────────────

    def set_curve_walk_active(self, active: bool) -> None:
        """Reflect the current queue curve-walk state on the button."""
        was = self._walk_btn.property("active")
        if was == active:
            return
        self._walk_btn.setProperty("active", active)
        self._walk_btn.setText("■  Curve Active" if active else "↺  Walk Curve")
        self._walk_btn.style().unpolish(self._walk_btn)
        self._walk_btn.style().polish(self._walk_btn)

    def set_arc_active(self, active: bool, shape_key: str = "FLAT") -> None:
        """Sync the arc mode toggle and shape selector to the given state."""
        self._arc_toggle_btn.setChecked(active)
        self._arc_toggle_btn.setText("Arc: ON" if active else "Arc: OFF")
        if shape_key in self._arc_shape_btns:
            self._arc_shape_btns[shape_key].setChecked(True)

    def _set_score_style(self, preview: bool) -> None:
        col = MUTED if preview else FG
        style = (
            f"color: {col}; font-size: 10px; font-family: Menlo, monospace; "
            f"border: none; background: transparent;"
        )
        self._d4a_val.setStyleSheet(style)
        self._d4b_val.setStyleSheet(style)

    def update_scores(
        self,
        d4_a:    float,
        d4_b:    float,
        bits:    np.ndarray,
        seg_idx: int,
        n_segs:  int,
        D1:      np.ndarray,
        D3:      np.ndarray,
        t:       Optional[float] = None,
        preview: bool = False,
    ) -> None:
        """Update all score / segment fields. preview=True → muted ghost style."""
        self._set_score_style(preview)

        self._d4a_val.setText(f"{d4_a:+.4f}")
        self._d4b_val.setText(f"{d4_b:+.4f}")
        self._d4a_gauge.set_value(d4_a, lo=-20.0, hi=20.0)

        for j, cell in enumerate(self._bit_cells):
            if j < len(bits):
                if bits[j] == 1.0:
                    cell.setText("■")
                    cell.setStyleSheet(
                        f"color: {ACC if not preview else MUTED}; font-size: 12px; "
                        f"font-family: Menlo, monospace; border: none; background: transparent;"
                    )
                else:
                    cell.setText("□")
                    cell.setStyleSheet(
                        f"color: {INDIGO if not preview else MUTED}; font-size: 12px; "
                        f"font-family: Menlo, monospace; border: none; background: transparent;"
                    )
            else:
                cell.setText("·")

        self._seg_val.setText(f"{seg_idx} / {n_segs - 1}")
        if t is not None:
            self._t_val.setText(f"{t:.3f}")
        self._d1_val.setText(f"({D1[0]:+.0f}, {D1[1]:+.0f})")
        self._d3_val.setText(f"({D3[0]:.1f}, {D3[1]:.1f})")

    def update_track(self, title: str, artist: str, has_track: bool) -> None:
        if artist and title:
            self._track_lbl.setText(f"♪  {artist} — {title}")
        elif title:
            self._track_lbl.setText(f"♪  {title}")
        else:
            self._track_lbl.setText("♪  no track")
        self._track_lbl.setStyleSheet(
            f"color: {FG if has_track else MUTED}; font-size: 9px; "
            f"border: none; background: transparent;"
        )
        self._anchor_btn.setEnabled(has_track)

    def set_anchor_status(
        self,
        anchored: bool,
        source:   str             = "manual",
        d4_a:     Optional[float] = None,
        bpm:      Optional[float] = None,
        key_sig:  Optional[str]   = None,
    ) -> None:
        self._anchored = anchored
        if not anchored:
            self._anchor_status.setText("")
            self._anchor_status.setStyleSheet(
                f"color: {METER_OK}; font-size: 8px; font-family: Menlo, monospace; "
                f"border: none; background: transparent;"
            )
            self._anchor_btn.setText("Anchor Track")
            return

        if source == "auto":
            parts = ["◦ bpm×key"]
            if bpm:
                parts.append(f"bpm {bpm:.0f}")
            if key_sig:
                parts.append(f"key {key_sig}")
            if d4_a is not None:
                parts.append(f"d4_a {d4_a:+.4f}")
            self._anchor_status.setText("  ".join(parts))
            self._anchor_status.setStyleSheet(
                f"color: {MUTED}; font-size: 8px; font-family: Menlo, monospace; "
                f"border: none; background: transparent;"
            )
            self._anchor_btn.setText("Override Position")
        else:
            txt = "✓ manual"
            if d4_a is not None:
                txt += f"  d4_a {d4_a:+.4f}"
            self._anchor_status.setText(txt)
            self._anchor_status.setStyleSheet(
                f"color: {METER_OK}; font-size: 8px; font-family: Menlo, monospace; "
                f"border: none; background: transparent;"
            )
            self._anchor_btn.setText("Re-anchor")

    def update_playback_t(self, t: float) -> None:
        self._t_val.setText(f"{t:.3f}")
