# -*- coding: utf-8 -*-
"""phi.ui.qt.sleep_timer — sleep timer engine + Qt dialog.

Replaces phi.ui.sleep_timer (Tkinter).

Public API
----------
    SleepTimer(schedule, on_expire, on_tick)  — framework-agnostic countdown
    SleepTimerDialog(parent, ctrl)            — QDialog
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from phi.config import ACC, ACC2, BG, CARD, CARD2, FG, MUTED

_PRESETS = [5, 10, 15, 30, 45, 60, 90]


# ── SleepTimer (engine) ───────────────────────────────────────────────────────

class SleepTimer:
    """
    Lightweight countdown timer driven by a Qt-compatible scheduler.

    schedule  : callable(ms, fn) — e.g. self._sched from _DispatchMixin
    on_expire : called when timer hits zero
    on_tick   : optional; called every second with remaining_secs (or None)
    """

    _TICK_MS = 1_000

    def __init__(
        self,
        schedule:  Callable,
        on_expire: Callable,
        on_tick:   Callable | None = None,
    ) -> None:
        self._schedule  = schedule
        self._on_expire = on_expire
        self._on_tick   = on_tick
        self._remaining: int | None = None

    def set(self, minutes: float) -> None:
        self.cancel()
        self._remaining = max(1, int(minutes * 60))
        self._tick()

    def cancel(self) -> None:
        self._remaining = None
        if self._on_tick:
            self._on_tick(None)

    def remaining(self) -> int | None:
        return self._remaining

    @property
    def active(self) -> bool:
        return self._remaining is not None

    def _tick(self) -> None:
        if self._remaining is None:
            return
        if self._remaining <= 0:
            self._remaining = None
            if self._on_tick:
                self._on_tick(None)
            self._on_expire()
            return
        if self._on_tick:
            self._on_tick(self._remaining)
        self._remaining -= 1
        self._schedule(self._TICK_MS, self._tick)


# ── SleepTimerDialog (Qt dialog) ──────────────────────────────────────────────

class SleepTimerDialog(QDialog):
    """
    Small modal for setting / cancelling the sleep timer.
    Shows preset buttons and a custom-minutes entry.
    """

    def __init__(self, parent: QWidget, ctrl: object = None) -> None:
        super().__init__(parent)
        self._ctrl = ctrl or (parent if hasattr(parent, "sleep_timer") else None)
        self.setWindowTitle("Sleep Timer")
        self.setModal(True)
        self.setFixedSize(300, 290)
        self.setStyleSheet(f"QDialog {{ background: {BG}; }}")
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(8)

        title = QLabel("Sleep Timer")
        title.setStyleSheet(f"color: {FG}; font-size: 13px; font-weight: bold;")
        root.addWidget(title)

        timer = getattr(self._ctrl, "sleep_timer", None)
        if timer and timer.active:
            rem = timer.remaining() or 0
            m, s = rem // 60, rem % 60
            active_lbl = QLabel(f"Active — {m}:{s:02d} remaining")
            active_lbl.setStyleSheet(f"color: {ACC}; font-size: 10px;")
            root.addWidget(active_lbl)

            cancel_btn = QPushButton("Cancel timer")
            cancel_btn.setStyleSheet(
                f"color: {FG}; background: {CARD2}; border: none; "
                f"border-radius: 3px; padding: 6px 16px; font-size: 10px;"
            )
            cancel_btn.clicked.connect(self._cancel)
            root.addWidget(cancel_btn)
        else:
            hint = QLabel("Stop playback after:")
            hint.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
            root.addWidget(hint)

        # Preset grid
        grid_w  = QWidget()
        grid_l  = QGridLayout(grid_w)
        grid_l.setSpacing(6)
        for i, mins in enumerate(_PRESETS):
            btn = QPushButton(f"{mins} min")
            btn.setStyleSheet(
                f"color: {FG}; background: {CARD}; border: none; "
                f"border-radius: 3px; padding: 6px 10px; font-size: 10px;"
            )
            btn.clicked.connect(lambda checked, m=mins: self._set(m))
            grid_l.addWidget(btn, i // 3, i % 3)
        root.addWidget(grid_w)

        # Custom entry
        custom_row = QHBoxLayout()
        custom_lbl = QLabel("Custom:")
        custom_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
        self._custom_edit = QLineEdit("20")
        self._custom_edit.setFixedWidth(50)
        self._custom_edit.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: 1px solid {ACC2}; "
            f"border-radius: 3px; padding: 3px 6px; font-size: 10px;"
        )
        min_lbl = QLabel("min")
        min_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
        custom_row.addWidget(custom_lbl)
        custom_row.addWidget(self._custom_edit)
        custom_row.addWidget(min_lbl)
        custom_row.addStretch()
        root.addLayout(custom_row)

        # Set button
        set_btn = QPushButton("Set timer")
        set_btn.setStyleSheet(
            f"color: #ffffff; background: {ACC}; border: none; "
            f"border-radius: 3px; padding: 8px 24px; "
            f"font-size: 11px; font-weight: bold;"
        )
        set_btn.clicked.connect(self._set_custom)
        root.addWidget(set_btn)
        root.addStretch()

    def _set(self, minutes: float) -> None:
        timer = getattr(self._ctrl, "sleep_timer", None)
        if timer:
            timer.set(minutes)
            if hasattr(self._ctrl, "_flash"):
                self._ctrl._flash(f"⏾ Sleep in {int(minutes)} min")  # type: ignore[union-attr]
        self.accept()

    def _set_custom(self) -> None:
        try:
            mins = int(self._custom_edit.text())
            if mins > 0:
                self._set(mins)
        except ValueError:
            pass

    def _cancel(self) -> None:
        timer = getattr(self._ctrl, "sleep_timer", None)
        if timer:
            timer.cancel()
            if hasattr(self._ctrl, "_flash"):
                self._ctrl._flash("⏾ Sleep timer cancelled")  # type: ignore[union-attr]
        self.accept()
