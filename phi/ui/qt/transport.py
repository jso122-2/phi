# -*- coding: utf-8 -*-
"""phi.ui.qt.transport — PySide6 transport bar.

Identical public API to phi.ui.transport.TransportPanel so every call site
in PhiMainWindow, PlaybackController, and PollEngine works unchanged.

Public API (mirrors TransportPanel)
------------------------------------
    set_seek(pos, duration)
    set_end(duration)
    reset_seek()
    set_playing(playing)
    set_shuffle(on)
    set_repeat(mode)
    set_mode_label(shuffle, repeat)
    set_volume(v)
    load_waveform(path)   # no-op — kept for compatibility
    is_seeking            # bool property
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from phi.config import ACC, FG, GOLD, MUTED, fmt_time, vol_icon

# Must match _NEXT_PREV_DEBOUNCE_S in phi/ui/_app/_transport.py.
# The mixin guard is a second line of defence; this Qt-level gate prevents
# multiple clicked() signals queued in the same event-loop tick from all
# passing the mixin's timestamp check before _last_next_at is written back.
_BTN_DEBOUNCE_MS = 450


class _VarCompat:
    """
    Drop-in shim for tk.DoubleVar used by _TransportMixin._apply_replay_gain,
    on_toggle_mute, and _WindowMixin._vol_step via transport._vol_var.get().
    """

    def __init__(self, getter: object) -> None:
        self._getter = getter

    def get(self) -> float:
        return self._getter()  # type: ignore[call-arg]

    def set(self, v: float) -> None:
        pass  # writes go through set_volume()


class TransportWidget(QWidget):
    """Seek bar · prev/play/next · shuffle/repeat · volume."""

    def __init__(self, ctrl: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctrl      = ctrl
        self._duration  = 0.0
        self._seeking   = False

        # One-shot timers that gate Next/Prev button clicks at the Qt level.
        # While the timer is active, subsequent clicked() signals are dropped
        # before they ever reach the mixin — closing the event-queue race where
        # many signals arrive in the same tick before _last_next_at is updated.
        self._next_gate = QTimer(self)
        self._next_gate.setSingleShot(True)
        self._next_gate.setInterval(_BTN_DEBOUNCE_MS)

        self._prev_gate = QTimer(self)
        self._prev_gate.setSingleShot(True)
        self._prev_gate.setInterval(_BTN_DEBOUNCE_MS)

        self._build()
        self._vol_var   = _VarCompat(lambda: self._vol_bar.value() / 100.0)

    # ── build ──────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 6, 20, 10)
        root.setSpacing(2)

        # ── seek row ──────────────────────────────────────────────────────────
        seek_row = QHBoxLayout()

        self._time_lbl = QLabel("0:00")
        self._time_lbl.setFixedWidth(36)
        self._time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._time_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")

        self._seek_bar = QSlider(Qt.Orientation.Horizontal)
        self._seek_bar.setRange(0, 10_000)
        self._seek_bar.setValue(0)
        self._seek_bar.sliderPressed.connect(self._on_seek_press)
        self._seek_bar.sliderReleased.connect(self._on_seek_release)
        self._seek_bar.sliderMoved.connect(self._on_seek_moved)

        self._end_lbl = QLabel("0:00")
        self._end_lbl.setFixedWidth(36)
        self._end_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")

        seek_row.addWidget(self._time_lbl)
        seek_row.addWidget(self._seek_bar, stretch=1)
        seek_row.addWidget(self._end_lbl)

        # ── transport buttons ─────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_row.setSpacing(0)

        self._prev_btn = QPushButton("⏮")
        self._play_btn = QPushButton("▶")
        self._next_btn = QPushButton("⏭")
        self._shuf_btn = QPushButton("⇀")
        self._rep_btn  = QPushButton("⇄")
        self._mode_lbl = QLabel("")
        self._mode_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")
        self._mode_lbl.setMinimumWidth(90)

        self._play_btn.setStyleSheet(
            f"font-size: 22px; color: {FG}; padding: 4px 14px;"
        )
        for b in (self._prev_btn, self._next_btn):
            b.setStyleSheet(
                f"font-size: 15px; color: {MUTED}; padding: 6px 10px;"
            )
        self._shuf_btn.setStyleSheet(
            f"font-size: 13px; color: {MUTED}; padding: 6px 8px;"
        )
        self._rep_btn.setStyleSheet(
            f"font-size: 13px; color: {MUTED}; padding: 6px 8px;"
        )

        self._prev_btn.clicked.connect(
            lambda: self._gated(self._prev_gate, self._ctrl.on_prev)
        )
        self._play_btn.clicked.connect(self._ctrl.on_play_pause)
        self._next_btn.clicked.connect(
            lambda: self._gated(self._next_gate, self._ctrl.on_next)
        )
        self._shuf_btn.clicked.connect(self._ctrl.on_toggle_shuffle)
        self._rep_btn.clicked.connect(self._ctrl.on_cycle_repeat)

        btn_row.addWidget(self._prev_btn)
        btn_row.addWidget(self._play_btn)
        btn_row.addWidget(self._next_btn)
        btn_row.addSpacing(24)
        btn_row.addWidget(self._shuf_btn)
        btn_row.addWidget(self._rep_btn)
        btn_row.addSpacing(8)
        btn_row.addWidget(self._mode_lbl)

        # ── volume row ────────────────────────────────────────────────────────
        vol_row = QHBoxLayout()
        vol_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vol_row.setSpacing(8)

        self._vol_icon_lbl = QLabel("[V]")
        self._vol_icon_lbl.setStyleSheet(f"color: {ACC}; font-size: 10px;")

        self._vol_bar = QSlider(Qt.Orientation.Horizontal)
        self._vol_bar.setRange(0, 100)
        self._vol_bar.setValue(70)
        self._vol_bar.setFixedWidth(200)
        self._vol_bar.valueChanged.connect(self._on_vol_changed)

        self._vol_pct_lbl = QLabel("70%")
        self._vol_pct_lbl.setFixedWidth(36)
        self._vol_pct_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")

        vol_row.addWidget(self._vol_icon_lbl)
        vol_row.addWidget(self._vol_bar)
        vol_row.addWidget(self._vol_pct_lbl)

        root.addLayout(seek_row)
        root.addLayout(btn_row)
        root.addLayout(vol_row)

    # ── button debounce gate ───────────────────────────────────────────────────

    @staticmethod
    def _gated(timer: QTimer, fn) -> None:
        """Call *fn* only if *timer* is not already running, then arm the timer."""
        if timer.isActive():
            return
        timer.start()
        fn()

    # ── public API (mirrors TransportPanel) ────────────────────────────────────

    @property
    def is_seeking(self) -> bool:
        return self._seeking

    def load_waveform(self, path: str) -> None:
        """No-op — kept for API compatibility."""

    def set_seek(self, pos: float, duration: float) -> None:
        if self._seeking:
            return
        self._duration = duration
        self._time_lbl.setText(fmt_time(pos))
        if duration > 0:
            self._seek_bar.blockSignals(True)
            self._seek_bar.setValue(int(pos / duration * 10_000))
            self._seek_bar.blockSignals(False)

    def set_end(self, duration: object) -> None:
        if isinstance(duration, (int, float)):
            self._duration = float(duration)
            self._end_lbl.setText(fmt_time(duration))
        else:
            self._end_lbl.setText(str(duration))

    def reset_seek(self) -> None:
        self._duration = 0.0
        self._time_lbl.setText("0:00")
        self._seek_bar.blockSignals(True)
        self._seek_bar.setValue(0)
        self._seek_bar.blockSignals(False)

    def set_playing(self, playing: bool) -> None:
        self._play_btn.setText("⏸" if playing else "▶")

    def set_shuffle(self, on: bool) -> None:
        """Backward-compat: delegates to set_shuffle_mode."""
        self.set_shuffle_mode("random" if on else "off")

    def set_shuffle_mode(self, mode: str) -> None:
        """Update shuffle button for the three-state cycle.

        off    → ⇀  MUTED  (inactive)
        random → ⇀  ACC    (random shuffle)
        cairrn → ↺  GOLD   (CAIRRN arc shuffle)
        """
        if mode == "cairrn":
            icon, color = "↺", GOLD
        elif mode == "random":
            icon, color = "⇀", ACC
        else:
            icon, color = "⇀", MUTED
        self._shuf_btn.setText(icon)
        self._shuf_btn.setStyleSheet(
            f"font-size: 13px; color: {color}; padding: 6px 8px;"
        )

    def set_repeat(self, mode: str) -> None:
        color = ACC if mode != "off" else MUTED
        self._rep_btn.setStyleSheet(
            f"font-size: 13px; color: {color}; padding: 6px 8px;"
        )

    def set_mode_label(self, shuffle: "bool | str", repeat: str) -> None:
        """Accept either a shuffle bool (legacy) or a shuffle_mode string."""
        parts: list[str] = []
        if shuffle == "cairrn":
            parts.append("cairrn ↺")
        elif shuffle == "random" or shuffle is True:
            parts.append("shuffle")
        if repeat != "off":
            parts.append(f"repeat {repeat}")
        self._mode_lbl.setText("  ".join(parts))

    def set_volume(self, v: float) -> None:
        self._vol_bar.blockSignals(True)
        self._vol_bar.setValue(int(v * 100))
        self._vol_bar.blockSignals(False)
        self._vol_icon_lbl.setText(vol_icon(v))
        self._vol_pct_lbl.setText(f"{int(v * 100)}%")

    # ── internal handlers ──────────────────────────────────────────────────────

    def _on_seek_press(self) -> None:
        self._seeking = True

    def _on_seek_release(self) -> None:
        self._seeking = False
        if self._duration > 0:
            frac = self._seek_bar.value() / 10_000
            self._ctrl.on_seek(frac * self._duration)

    def _on_seek_moved(self, value: int) -> None:
        if self._seeking and self._duration > 0:
            self._time_lbl.setText(fmt_time(value / 10_000 * self._duration))
            self._ctrl.on_seek(value / 10_000 * self._duration)

    def _on_vol_changed(self, value: int) -> None:
        self._ctrl.on_volume(value / 100.0)
