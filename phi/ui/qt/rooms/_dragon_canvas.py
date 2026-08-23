# -*- coding: utf-8 -*-
"""phi.ui.qt.rooms._dragon_canvas — Dragon Curve canvas widgets.

Exports:
    _GaugeBar         — 3 px horizontal fill bar
    DragonCurveCanvas — QPainter canvas with scatter, beat rings, playback cursor
"""
from __future__ import annotations

import math
import time
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, QPointF, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from phi.config import (
    ACC, ACC2, BG, CARD2,
    GOLD, INDIGO, MUTED, VIOLET,
    METER_OK, METER_WARN, METER_CRIT,
)
from phi.models.dragon_curve import DragonCurve


# ─────────────────────────────────────────────────────────────────────────────
# Tiny gauge bar widget
# ─────────────────────────────────────────────────────────────────────────────

class _GaugeBar(QWidget):
    """
    3 px-high horizontal fill bar.

    Call set_value(v, lo, hi) to update; value is clamped and normalised to
    [lo, hi] before rendering.
    """

    def __init__(self, color: str = ACC, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(3)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._frac  = 0.0
        self._color = QColor(color)
        self._bg    = QColor(CARD2)

    def set_value(self, v: float, lo: float = -20.0, hi: float = 20.0) -> None:
        span = hi - lo
        self._frac = max(0.0, min(1.0, (v - lo) / span if span > 0 else 0.0))
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.fillRect(0, 0, self.width(), self.height(), self._bg)
        fill_w = max(0, int(self._frac * self.width()))
        if fill_w:
            p.fillRect(0, 0, fill_w, self.height(), self._color)
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# Dragon curve canvas
# ─────────────────────────────────────────────────────────────────────────────

class DragonCurveCanvas(QWidget):
    """
    Paints the dragon curve as coloured line segments.

    Overlay z-order (bottom → top):
        1. curve segments      — ACC/INDIGO by fold bit
        2. scatter dots        — library tracks by BPM colour, semi-transparent
        3. beat rings          — expanding rings from anchor at track BPM tempo
        4. playback cursor     — violet pulse, walks curve with playback pos
        5. hover ghost         — muted circle on mouse hover (non-committing)
        6. committed query dot — gold, persists after click

    Signals
    -------
        queried(d4_a, d4_b, bits, seg_idx)    — mouse click (commit query)
        hovered(d4_a, d4_b, bits, seg_idx)    — mouse hover over curve
        scatter_hovered(meta: dict, path: str) — mouse hover over a scatter dot
    """

    queried         = Signal(float, float, object, int)
    hovered         = Signal(float, float, object, int)
    scatter_hovered = Signal(dict, str)

    _PAD            = 24
    _PULSE_HZ       = 1.0
    _PULSE_RANGE    = 4.0
    _BEAT_DECAY_MS  = 220
    _BEAT_R_START   = 4.0
    _BEAT_R_END     = 22.0
    _BEAT_ALPHA     = 160
    _SCATTER_HIT_R  = 8.0
    _SCATTER_R      = 2.5

    def __init__(self, depth: int = 8, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(280, 280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background: {BG};")
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._depth   = depth
        self._dc      = DragonCurve(depth=depth)

        self._query_pt:  Optional[QPointF] = None
        self._hover_pt:  Optional[QPointF] = None
        self._play_pt:   Optional[QPointF] = None
        self._play_norm: Optional[tuple[float, float]] = None

        self._col_right = QColor(ACC)
        self._col_left  = QColor(INDIGO)
        self._col_query = QColor(GOLD)
        self._col_hover = QColor(MUTED)
        self._col_play  = QColor(VIOLET)

        self._pulse_phase  = 0.0
        self._pulse_timer  = QTimer(self)
        self._pulse_timer.setInterval(40)
        self._pulse_timer.timeout.connect(self._tick_pulse)

        self._beat_timer   = QTimer(self)
        self._beat_timer.setSingleShot(False)
        self._beat_timer.timeout.connect(self._on_beat)
        self._current_bpm: float = 0.0

        self._rings: list[tuple[QPointF, float]] = []

        self._scatter_unit:  Optional[np.ndarray] = None
        self._scatter_bpms:  Optional[np.ndarray] = None
        self._scatter_zones: Optional[np.ndarray] = None
        self._scatter_meta:  list[dict]            = []
        self._scatter_hover_idx: int               = -1

    # ── zone palette ─────────────────────────────────────────────────────────

    @staticmethod
    def _zone_color(zone_id: int) -> QColor:
        """Thin 1 px outline colour for scatter zone rings (zone 0–7)."""
        _ZONE_HEX = [
            INDIGO, ACC, GOLD, VIOLET,
            METER_OK, METER_WARN, METER_CRIT, ACC2,
        ]
        c = QColor(_ZONE_HEX[zone_id % len(_ZONE_HEX)])
        c.setAlpha(180)
        return c

    # ── depth ─────────────────────────────────────────────────────────────────

    @property
    def depth(self) -> int:
        return self._depth

    def set_depth(self, depth: int) -> None:
        if depth == self._depth:
            return
        self._depth    = depth
        self._dc       = DragonCurve(depth=depth)
        self._query_pt = None
        self._hover_pt = None
        self._play_pt  = None
        self._play_norm = None
        self.update()

    # ── coordinate helpers ────────────────────────────────────────────────────

    def _bb(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        pts = self._dc.points
        lo  = pts.min(axis=0)
        hi  = pts.max(axis=0)
        rng = np.maximum(hi - lo, 1e-9)
        return lo, hi, rng

    def _curve_to_canvas(self, cx: float, cy: float) -> QPointF:
        lo, _, rng = self._bb()
        pad = self._PAD
        w   = max(self.width()  - 2 * pad, 1)
        h   = max(self.height() - 2 * pad, 1)
        sx  = (cx - lo[0]) / rng[0] * w + pad
        sy  = (1.0 - (cy - lo[1]) / rng[1]) * h + pad
        return QPointF(sx, sy)

    def _canvas_to_curve(self, px: float, py: float) -> tuple[float, float]:
        lo, _, rng = self._bb()
        pad = self._PAD
        w   = max(self.width()  - 2 * pad, 1)
        h   = max(self.height() - 2 * pad, 1)
        cx  = (px - pad) / w * rng[0] + lo[0]
        cy  = (1.0 - (py - pad) / h) * rng[1] + lo[1]
        return float(cx), float(cy)

    def _seg_to_canvas(self, seg_idx: int) -> QPointF:
        """Canvas point for the midpoint of segment seg_idx."""
        pts = self._dc.points
        i   = min(seg_idx, len(pts) - 2)
        mid = (pts[i] + pts[i + 1]) * 0.5
        return self._curve_to_canvas(float(mid[0]), float(mid[1]))

    def _units_to_canvas_vec(self, xy: np.ndarray) -> np.ndarray:
        """
        Vectorized unit-space → canvas-pixel conversion.

        Args:
            xy: (N, 2) float64 in [0, 1]²
        Returns:
            (N, 2) float64 canvas pixel coords
        """
        pad = self._PAD
        w   = max(self.width()  - 2 * pad, 1)
        h   = max(self.height() - 2 * pad, 1)
        out = np.empty_like(xy)
        out[:, 0] = xy[:, 0] * w + pad
        out[:, 1] = (1.0 - xy[:, 1]) * h + pad
        return out

    @staticmethod
    def _bpm_color(bpm: float) -> QColor:
        """Colour-code a dot by BPM range."""
        if bpm <= 0:
            c = QColor(MUTED)
        elif bpm < 100:
            c = QColor(INDIGO)
        elif bpm < 130:
            c = QColor(ACC)
        elif bpm < 160:
            c = QColor(GOLD)
        else:
            c = QColor(METER_CRIT)
        c.setAlpha(100)
        return c

    def _query_at_canvas(self, px: float, py: float) -> tuple[int, float, float, np.ndarray]:
        """Return (seg_idx, d4_a, d4_b, bits) for a canvas-coords click/hover."""
        cx, cy = self._canvas_to_curve(px, py)
        lo, hi, _ = self._bb()
        cx = float(np.clip(cx, lo[0], hi[0]))
        cy = float(np.clip(cy, lo[1], hi[1]))
        seg         = self._dc.nearest_segment(cx, cy)
        D1, D2, D3  = self._dc.d1_d2_d3(seg)
        return (
            seg,
            self._dc.score_a(D1, D2, D3),
            self._dc.score_b(D1, D2, D3),
            self._dc.fold_bits(seg),
        )

    # ── playback cursor ───────────────────────────────────────────────────────

    def set_playback(self, t: Optional[float]) -> None:
        """Update the playback cursor from normalised position t ∈ [0, 1]."""
        if t is None:
            self._play_pt   = None
            self._play_norm = None
            self._pulse_timer.stop()
            self.update()
            return

        seg = int(max(0, min(self._dc.n_segments - 1, t * self._dc.n_segments)))
        self._play_pt = self._seg_to_canvas(seg)
        pts  = self._dc.points
        lo   = pts.min(axis=0)
        rng  = np.maximum(pts.max(axis=0) - lo, 1e-9)
        mid  = (pts[seg] + pts[seg + 1]) * 0.5
        self._play_norm = (
            float((mid[0] - lo[0]) / rng[0]),
            float((mid[1] - lo[1]) / rng[1]),
        )
        if not self._pulse_timer.isActive():
            self._pulse_timer.start()
        self.update()

    def set_anchor(self, x_norm: Optional[float], y_norm: Optional[float]) -> None:
        """Set a persisted anchor point (saved clipper_x / clipper_y)."""
        if x_norm is None or y_norm is None:
            self._query_pt = None
        else:
            cx, cy         = self._dc.unit_to_curve(float(x_norm), float(y_norm))
            self._query_pt = self._curve_to_canvas(cx, cy)
        self.update()

    # ── BPM heartbeat ─────────────────────────────────────────────────────────

    def set_bpm(self, bpm: Optional[float]) -> None:
        """Start the BPM beat timer. Pass None or 0 to stop."""
        bpm_f = float(bpm) if bpm else 0.0
        self._current_bpm = bpm_f

        if bpm_f < 20 or bpm_f > 400:
            self._beat_timer.stop()
            return

        interval_ms = max(150, int(60_000 / bpm_f))
        if self._beat_timer.interval() != interval_ms:
            self._beat_timer.setInterval(interval_ms)
        if not self._beat_timer.isActive():
            self._beat_timer.start()

    def _on_beat(self) -> None:
        centre = self._query_pt or self._play_pt
        if centre is None:
            return
        self._rings.append((QPointF(centre.x(), centre.y()), time.monotonic()))
        if not self._pulse_timer.isActive():
            self._pulse_timer.start()

    # ── scatter ───────────────────────────────────────────────────────────────

    def load_scatter(self, data: list[dict]) -> None:
        """
        Load library tracks for the scatter overlay.

        Each dict must have: clipper_x, clipper_y, bpm, path.
        """
        if not data:
            self._scatter_unit  = None
            self._scatter_bpms  = None
            self._scatter_zones = None
            self._scatter_meta  = []
            self._scatter_hover_idx = -1
            self.update()
            return

        self._scatter_unit = np.array(
            [[d["clipper_x"], d["clipper_y"]] for d in data], dtype=np.float64,
        )
        self._scatter_bpms = np.array(
            [float(d.get("bpm") or 0) for d in data], dtype=np.float64,
        )
        self._scatter_zones = np.array(
            [int(d.get("zone_id", -1)) for d in data], dtype=np.int32,
        )
        self._scatter_meta      = list(data)
        self._scatter_hover_idx = -1
        self.update()

    # ── animation ────────────────────────────────────────────────────────────

    def _tick_pulse(self) -> None:
        now = time.monotonic()
        self._pulse_phase = (
            self._pulse_phase + 2 * math.pi * self._PULSE_HZ * 0.04
        ) % (2 * math.pi)
        decay_s = self._BEAT_DECAY_MS / 1000.0
        self._rings = [(c, t) for c, t in self._rings if now - t < decay_s]
        if not self._rings and not self._play_pt:
            self._pulse_timer.stop()
        self.update()

    # ── events ────────────────────────────────────────────────────────────────

    def mouseMoveEvent(self, event) -> None:
        pos  = event.position()
        px, py = pos.x(), pos.y()

        if self._scatter_unit is not None and len(self._scatter_unit) > 0:
            canvas_xy = self._units_to_canvas_vec(self._scatter_unit)
            dx = canvas_xy[:, 0] - px
            dy = canvas_xy[:, 1] - py
            dists_sq = dx * dx + dy * dy
            nearest = int(np.argmin(dists_sq))
            if dists_sq[nearest] <= self._SCATTER_HIT_R ** 2:
                if self._scatter_hover_idx != nearest:
                    self._scatter_hover_idx = nearest
                    self._hover_pt = None
                    self.update()
                self.scatter_hovered.emit(
                    self._scatter_meta[nearest],
                    self._scatter_meta[nearest].get("path", ""),
                )
                return
            else:
                if self._scatter_hover_idx != -1:
                    self._scatter_hover_idx = -1
                    self.update()

        seg, d4_a, d4_b, bits = self._query_at_canvas(px, py)
        self._hover_pt = self._seg_to_canvas(seg)
        self._scatter_hover_idx = -1
        self.update()
        self.hovered.emit(d4_a, d4_b, bits, seg)

    def leaveEvent(self, event) -> None:
        self._hover_pt          = None
        self._scatter_hover_idx = -1
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        pos = event.position()
        seg, d4_a, d4_b, bits = self._query_at_canvas(pos.x(), pos.y())
        self._query_pt = self._seg_to_canvas(seg)
        self._hover_pt = None
        self.update()
        self.queried.emit(d4_a, d4_b, bits, seg)

    def resizeEvent(self, event) -> None:
        if self._play_norm is not None:
            x_n, y_n = self._play_norm
            cx, cy   = self._dc.unit_to_curve(x_n, y_n)
            self._play_pt = self._curve_to_canvas(cx, cy)
        super().resizeEvent(event)

    # ── painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        pts      = self._dc.points
        fold_seq = self._dc._fold_seq
        n_segs   = self._dc.n_segments

        # 1. Curve segments
        canvas_pts = [
            self._curve_to_canvas(float(pts[i, 0]), float(pts[i, 1]))
            for i in range(len(pts))
        ]
        pen = QPen()
        pen.setWidthF(1.2)
        for i in range(n_segs):
            bit = int(fold_seq[min(i, len(fold_seq) - 1)])
            pen.setColor(self._col_right if bit == 1 else self._col_left)
            p.setPen(pen)
            p.drawLine(canvas_pts[i], canvas_pts[i + 1])

        # 2. Library scatter dots
        if self._scatter_unit is not None and len(self._scatter_unit) > 0:
            canvas_xy = self._units_to_canvas_vec(self._scatter_unit)
            p.setPen(Qt.PenStyle.NoPen)
            for i, (cx, cy) in enumerate(canvas_xy):
                if i == self._scatter_hover_idx:
                    continue
                bpm  = float(self._scatter_bpms[i]) if self._scatter_bpms is not None else 0.0
                col  = self._bpm_color(bpm)
                p.setBrush(col)
                p.drawEllipse(QPointF(cx, cy), self._SCATTER_R, self._SCATTER_R)

                if self._scatter_zones is not None:
                    zone_id = int(self._scatter_zones[i])
                    if zone_id >= 0:
                        p.setPen(QPen(self._zone_color(zone_id), 1.0))
                        p.setBrush(Qt.BrushStyle.NoBrush)
                        p.drawEllipse(QPointF(cx, cy), self._SCATTER_R + 1.5, self._SCATTER_R + 1.5)
                        p.setPen(Qt.PenStyle.NoPen)
                        p.setBrush(Qt.BrushStyle.NoBrush)

            idx = self._scatter_hover_idx
            if 0 <= idx < len(canvas_xy):
                bpm = float(self._scatter_bpms[idx]) if self._scatter_bpms is not None else 0.0
                col = self._bpm_color(bpm)
                col.setAlpha(220)
                ring_c = QColor(col)
                ring_c.setAlpha(140)
                p.setPen(QPen(ring_c, 1.0))
                p.setBrush(col)
                cx, cy = canvas_xy[idx]
                p.drawEllipse(QPointF(cx, cy), self._SCATTER_R + 2.5, self._SCATTER_R + 2.5)
                if self._scatter_zones is not None:
                    zone_id = int(self._scatter_zones[idx])
                    if zone_id >= 0:
                        zc = self._zone_color(zone_id)
                        zc.setAlpha(220)
                        p.setPen(QPen(zc, 1.5))
                        p.setBrush(Qt.BrushStyle.NoBrush)
                        p.drawEllipse(QPointF(cx, cy), self._SCATTER_R + 4.5, self._SCATTER_R + 4.5)
                p.setPen(Qt.PenStyle.NoPen)

        # 3. Beat rings
        if self._rings:
            now      = time.monotonic()
            decay_s  = self._BEAT_DECAY_MS / 1000.0
            r_range  = self._BEAT_R_END - self._BEAT_R_START
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            for centre, t_birth in self._rings:
                elapsed = now - t_birth
                frac    = min(1.0, elapsed / decay_s)
                radius  = self._BEAT_R_START + frac * r_range
                alpha   = int(self._BEAT_ALPHA * (1.0 - frac))
                ring_col = QColor(VIOLET)
                ring_col.setAlpha(alpha)
                p.setPen(QPen(ring_col, 1.2))
                p.drawEllipse(centre, radius, radius)
            p.setPen(Qt.PenStyle.NoPen)

        # 4. Playback cursor
        if self._play_pt is not None:
            pulse_r  = 6.0 + self._PULSE_RANGE * (0.5 + 0.5 * math.sin(self._pulse_phase))
            ring_col = QColor(VIOLET)
            ring_col.setAlpha(80)
            p.setPen(QPen(ring_col, 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(self._play_pt, pulse_r, pulse_r)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._col_play)
            p.drawEllipse(self._play_pt, 4.5, 4.5)

        # 5. Hover ghost
        if self._hover_pt is not None:
            ghost_col = QColor(MUTED)
            ghost_col.setAlpha(120)
            p.setPen(QPen(ghost_col, 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(self._hover_pt, 5.0, 5.0)

        # 6. Committed query dot
        if self._query_pt is not None:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._col_query)
            p.drawEllipse(self._query_pt, 4.0, 4.0)

        p.end()
