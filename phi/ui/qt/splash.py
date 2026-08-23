# -*- coding: utf-8 -*-
"""phi.ui.qt.splash — golden-ratio φ splash screen.

Non-blocking: start_pulse() ticks on a QTimer while PhiMainWindow constructs.
splash.finish(window) dissolves it the moment the window is ready.
"""
from __future__ import annotations

import math
import pathlib

from PySide6.QtCore import Qt, QRect, QTimer
from PySide6.QtGui import (
    QColor, QPainter, QPixmap,
    QRadialGradient, QBrush,
)
from PySide6.QtWidgets import QSplashScreen


_RESOURCES  = pathlib.Path(__file__).parent.parent.parent / "resources"
_ICON_PNG   = _RESOURCES / "phi_icon.png"

_W: int = 800
_H: int = 800

_TICK_MS        = 30    # ms per frame
_FADE_TICKS     = 40    # 40 × 30 ms = 1.2 s fade-in

_GOLD_R, _GOLD_G, _GOLD_B = 218, 165, 32


def _load_base_pixmap() -> QPixmap:
    """Load phi_icon.png scaled to the splash canvas."""
    if _ICON_PNG.exists():
        px = QPixmap(str(_ICON_PNG))
        if not px.isNull():
            return px.scaled(
                _W, _H,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
    # graceful fallback: plain gold φ on black
    px = QPixmap(_W, _H)
    px.fill(QColor(13, 13, 13))
    p = QPainter(px)
    from PySide6.QtGui import QFont
    f = QFont("Helvetica Neue", 400)
    f.setBold(False)
    p.setFont(f)
    p.setPen(QColor(_GOLD_R, _GOLD_G, _GOLD_B))
    p.drawText(QRect(0, 0, _W, _H), Qt.AlignmentFlag.AlignCenter, "φ")
    p.end()
    return px


class PhiSplashScreen(QSplashScreen):
    """
    Golden-ratio φ splash with animated glow.

    Usage in ``__main__``::

        splash = PhiSplashScreen()
        splash.show()
        app.processEvents()
        splash.start_pulse()      # non-blocking; construction happens underneath
        window = PhiMainWindow()
        window.show()
        splash.finish(window)     # splash dissolves
    """

    def __init__(self) -> None:
        # Black canvas — image painted in drawContents()
        base = QPixmap(_W, _H)
        base.fill(Qt.GlobalColor.black)
        super().__init__(
            base,
            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint,
        )

        self._tick:        int   = 0
        self._pulse_phase: float = 0.0
        self._icon: QPixmap      = _load_base_pixmap()
        self._ticker: QTimer | None = None

        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            g = screen.geometry()
            self.move(
                g.x() + (g.width()  - _W) // 2,
                g.y() + (g.height() - _H) // 2,
            )

    # ── public ────────────────────────────────────────────────────────────────

    def start_pulse(self) -> None:
        """Start the fade + glow on a QTimer. Returns immediately."""
        if self._ticker is not None:
            return
        ticker = QTimer(self)
        ticker.setInterval(_TICK_MS)
        ticker.timeout.connect(self._on_tick)
        ticker.start()
        self._ticker = ticker
        self._on_tick()

    def animate(self) -> None:
        """Back-compat alias for start_pulse() — does not block."""
        self.start_pulse()

    def finish(self, widget) -> None:  # type: ignore[override]
        if self._ticker is not None:
            self._ticker.stop()
            self._ticker = None
        super().finish(widget)

    # ── Qt paint hook ─────────────────────────────────────────────────────────

    def drawContents(self, painter: QPainter) -> None:
        # ── black background ──────────────────────────────────────────────────
        painter.fillRect(QRect(0, 0, _W, _H), QColor(0, 0, 0))

        # ── φ image with fade-in ──────────────────────────────────────────────
        alpha = min(1.0, self._tick / max(1, _FADE_TICKS))
        painter.setOpacity(alpha)
        ix = (_W - self._icon.width())  // 2
        iy = (_H - self._icon.height()) // 2
        painter.drawPixmap(ix, iy, self._icon)
        painter.setOpacity(1.0)

        # ── gold radial glow — breathes once image is fully visible ───────────
        if self._tick >= _FADE_TICKS:
            glow_a = 0.12 + 0.10 * math.sin(self._pulse_phase)
            cx, cy = _W / 2, _H / 2
            radius = _W * 0.52

            grad = QRadialGradient(cx, cy, radius)
            gold_glow = QColor(_GOLD_R, _GOLD_G, _GOLD_B, int(glow_a * 255))
            grad.setColorAt(0.55, gold_glow)
            grad.setColorAt(1.00, QColor(0, 0, 0, 0))

            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_Screen
            )
            painter.drawEllipse(
                int(cx - radius), int(cy - radius),
                int(radius * 2),  int(radius * 2),
            )
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver
            )

    # ── private ───────────────────────────────────────────────────────────────

    def _on_tick(self) -> None:
        self._tick += 1
        if self._tick >= _FADE_TICKS:
            self._pulse_phase += 0.13   # ~0.7 Hz at 30 ms tick
        self.repaint()
