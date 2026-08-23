# -*- coding: utf-8 -*-
"""phi.ui.qt.rooms._mini_transport — slim Qt transport bar for room pages.

Replaces phi.ui.rooms.mini_transport.MiniTransport (tk.Frame).

Public API (mirrors MiniTransport)
------------------------------------
    sync(title, artist, playing, pos, duration)
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from phi.config import ACC, ACC2, CARD2, FG, MUTED, fmt_time

_BTN_DEBOUNCE_MS = 450   # matches TransportWidget and _NEXT_PREV_DEBOUNCE_S


class MiniTransportWidget(QWidget):
    """
    Slim transport bar pinned to the bottom of room pages.

    ┌─────────────────────────────────────────────────────┐
    │ ♪ Artist — Title          ◀◀  ▶  ▶▶                │
    │ ████░░░░░░░░░░  progress                            │
    └─────────────────────────────────────────────────────┘
    """

    def __init__(self, ctrl: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctrl     = ctrl
        self._duration = 0.0

        self._next_gate = QTimer(self)
        self._next_gate.setSingleShot(True)
        self._next_gate.setInterval(_BTN_DEBOUNCE_MS)

        self._prev_gate = QTimer(self)
        self._prev_gate.setSingleShot(True)
        self._prev_gate.setInterval(_BTN_DEBOUNCE_MS)

        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Progress bar (2 px strip at the very top of the widget)
        self._prog_bar = QWidget()
        self._prog_bar.setFixedHeight(2)
        self._prog_bar.setStyleSheet(f"background: {ACC2};")
        root.addWidget(self._prog_bar)

        # Main row
        self.setStyleSheet(f"background: {CARD2};")
        row = QHBoxLayout()
        row.setContentsMargins(12, 6, 12, 6)
        row.setSpacing(8)

        self._track_lbl = QLabel("—")
        self._track_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
        self._track_lbl.setMinimumWidth(0)

        btn_style = f"color: {MUTED}; font-size: 13px; padding: 0 6px; border: none; background: transparent;"
        act_style = f"color: {FG}; font-size: 13px; padding: 0 6px; border: none; background: transparent;"

        self._prev_btn = QPushButton("⏮")
        self._play_btn = QPushButton("▶")
        self._next_btn = QPushButton("⏭")
        for b in (self._prev_btn, self._next_btn):
            b.setStyleSheet(btn_style)
        self._play_btn.setStyleSheet(act_style)

        self._prev_btn.clicked.connect(
            lambda: self._gated(self._prev_gate, self._ctrl.on_prev)
        )
        self._play_btn.clicked.connect(self._ctrl.on_play_pause)
        self._next_btn.clicked.connect(
            lambda: self._gated(self._next_gate, self._ctrl.on_next)
        )

        self._time_lbl = QLabel("0:00")
        self._time_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")
        self._time_lbl.setFixedWidth(32)
        self._time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        row.addWidget(self._track_lbl, stretch=1)
        row.addWidget(self._prev_btn)
        row.addWidget(self._play_btn)
        row.addWidget(self._next_btn)
        row.addWidget(self._time_lbl)
        root.addLayout(row)

    # ── button debounce gate ───────────────────────────────────────────────────

    @staticmethod
    def _gated(timer: QTimer, fn) -> None:
        if timer.isActive():
            return
        timer.start()
        fn()

    # ── public ────────────────────────────────────────────────────────────────

    def sync(
        self,
        title:    str,
        artist:   str,
        playing:  bool,
        pos:      float,
        duration: float,
    ) -> None:
        self._duration = duration

        if artist:
            label = f"♪  {artist} — {title}"
        elif title:
            label = f"♪  {title}"
        else:
            label = "—"
        self._track_lbl.setText(label)
        self._play_btn.setText("⏸" if playing else "▶")
        self._time_lbl.setText(fmt_time(pos))

        if duration > 0:
            frac = max(0.0, min(1.0, pos / duration))
            w    = self._prog_bar.parent().width() if self._prog_bar.parent() else 0
            self._prog_bar.setFixedWidth(max(0, int(frac * w)))
