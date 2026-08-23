# -*- coding: utf-8 -*-
"""phi.ui.qt.rooms.inference_room — ML Inference room.

Runs SongDerivativeModel.score_library() in a background QThread and
displays the ranked D1–D4 score table for every track in the library.

Layout
------
┌──────────────────────────────────────────────────────────────────────┐
│  INFERENCE        ‹ Dragon · Inference · Forge ›         [Run Scores]│
├───────────────────────────────────────┬──────────────────────────────┤
│  D4  D3  D1  D2  title / artist       │  SELECTED TRACK              │
│  ████▒░░  ████▒░░  …                  │  D4  ████████▒░░ 0.842        │
│  (playing row highlighted in ACC)     │  D3  ██████░░░░ 0.731         │
│  …                                    │  D1  ████████░░ 0.805         │
│                                       │  D2  ██████░░░░ 0.657         │
│                                       │                               │
│                                       │  target  0.912                │
│                                       │  zone    3                    │
├───────────────────────────────────────┴──────────────────────────────┤
│  mini transport                                                        │
└──────────────────────────────────────────────────────────────────────┘

Room protocol: on_show(), on_refresh(), sync_transport(), mark_playing()
"""
from __future__ import annotations

import os
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from phi.config import (
    ACC, ACC2, BG, CARD, CARD2, BORDER,
    FG, GOLD, INDIGO, MUTED, VIOLET,
    METER_OK, METER_WARN, METER_CRIT,
)
from phi.ui.qt.rooms._mini_transport import MiniTransportWidget


# ─────────────────────────────────────────────────────────────────────────────
# Route constants (shared with dragon_room / forge_room)
# ─────────────────────────────────────────────────────────────────────────────

_ROUTE     = ["Dragon", "Inference", "Forge"]
_ROUTE_IDX = 1   # Inference is index 1


# ─────────────────────────────────────────────────────────────────────────────
# Background worker
# ─────────────────────────────────────────────────────────────────────────────

class _ScoreWorker(QThread):
    """Compute D1–D4 scores for the library in a background thread."""

    finished = Signal(dict)   # dict[path, {d1, d2, d3, d4, target}]
    error    = Signal(str)

    def __init__(self, paths: list[str], parent=None) -> None:
        super().__init__(parent)
        self._paths = paths

    def run(self) -> None:
        try:
            from phi.models.song_derivative import SongDerivativeModel
            model  = SongDerivativeModel()
            scores = model.score_library(self._paths)
            self.finished.emit(scores)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Tiny score bar (reused from dragon_room pattern)
# ─────────────────────────────────────────────────────────────────────────────

class _Bar(QWidget):
    def __init__(self, color: str = ACC, height: int = 3, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._frac  = 0.0
        from PySide6.QtGui import QPainter
        self._color = QColor(color)
        self._bg    = QColor(CARD2)

    def set_frac(self, v: float) -> None:
        self._frac = max(0.0, min(1.0, v))
        self.update()

    def paintEvent(self, _event) -> None:
        from PySide6.QtGui import QPainter
        p = QPainter(self)
        p.fillRect(0, 0, self.width(), self.height(), self._bg)
        w = max(0, int(self._frac * self.width()))
        if w:
            p.fillRect(0, 0, w, self.height(), self._color)
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# Detail panel (right side)
# ─────────────────────────────────────────────────────────────────────────────

class _DetailPanel(QWidget):
    _W = 220

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(self._W)
        self.setStyleSheet(f"background: {CARD}; border-left: 1px solid {BORDER};")
        self._build()

    @staticmethod
    def _sep(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {ACC}; font-size: 8px; letter-spacing: 2px; "
            "border: none; background: transparent;"
        )
        return lbl

    def _bar_row(self, root: QVBoxLayout, key: str, color: str) -> tuple[QLabel, _Bar]:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        k = QLabel(key)
        k.setFixedWidth(22)
        k.setStyleSheet(f"color: {MUTED}; font-size: 9px; border: none; background: transparent;")
        v = QLabel("—")
        v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        v.setStyleSheet(f"color: {FG}; font-size: 9px; font-family: Menlo, monospace; "
                        "border: none; background: transparent;")
        row.addWidget(k)
        row.addWidget(v, stretch=1)
        root.addLayout(row)
        bar = _Bar(color, height=3, parent=self)
        root.addWidget(bar)
        root.addSpacing(4)
        return v, bar

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 16, 14, 12)
        root.setSpacing(4)

        root.addWidget(self._sep("SELECTED TRACK"))
        self._title_lbl = QLabel("no selection")
        self._title_lbl.setWordWrap(True)
        self._title_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; border: none; background: transparent;"
        )
        root.addWidget(self._title_lbl)
        root.addSpacing(10)

        root.addWidget(self._sep("SCORES"))
        self._d4_val, self._d4_bar = self._bar_row(root, "D4", ACC)
        self._d3_val, self._d3_bar = self._bar_row(root, "D3", INDIGO)
        self._d1_val, self._d1_bar = self._bar_row(root, "D1", GOLD)
        self._d2_val, self._d2_bar = self._bar_row(root, "D2", VIOLET)
        root.addSpacing(10)

        root.addWidget(self._sep("META"))
        self._target_val = self._kv(root, "target")
        self._zone_val   = self._kv(root, "zone")

        root.addStretch()

    def _kv(self, root: QVBoxLayout, key: str) -> QLabel:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        k = QLabel(key)
        k.setStyleSheet(f"color: {MUTED}; font-size: 9px; border: none; background: transparent;")
        v = QLabel("—")
        v.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        v.setStyleSheet(f"color: {FG}; font-size: 9px; font-family: Menlo, monospace; "
                        "border: none; background: transparent;")
        row.addWidget(k)
        row.addWidget(v, stretch=1)
        root.addLayout(row)
        return v

    def show_track(self, title: str, artist: str, scores: dict, zone: int = -1) -> None:
        if artist and title:
            self._title_lbl.setText(f"♪  {artist} — {title}")
        elif title:
            self._title_lbl.setText(f"♪  {title}")
        else:
            self._title_lbl.setText("♪  no selection")

        for key, val_lbl, bar in [
            ("d4", self._d4_val, self._d4_bar),
            ("d3", self._d3_val, self._d3_bar),
            ("d1", self._d1_val, self._d1_bar),
            ("d2", self._d2_val, self._d2_bar),
        ]:
            v = scores.get(key)
            if v is not None:
                val_lbl.setText(f"{v:.3f}")
                bar.set_frac(float(v))
            else:
                val_lbl.setText("—")
                bar.set_frac(0.0)

        t = scores.get("target")
        self._target_val.setText(f"{t:.3f}" if t is not None else "—")
        self._zone_val.setText(str(zone) if zone >= 0 else "—")

    def clear(self) -> None:
        self._title_lbl.setText("no selection")
        for lbl in (self._d4_val, self._d3_val, self._d1_val, self._d2_val):
            lbl.setText("—")
        for bar in (self._d4_bar, self._d3_bar, self._d1_bar, self._d2_bar):
            bar.set_frac(0.0)
        self._target_val.setText("—")
        self._zone_val.setText("—")


# ─────────────────────────────────────────────────────────────────────────────
# Track list row
# ─────────────────────────────────────────────────────────────────────────────

def _score_block(v: Optional[float], width: int = 4) -> str:
    """Tiny ASCII bar: ████░░░░ style, *width* chars wide."""
    if v is None:
        return "—" * width
    filled = int(round(v * width))
    return "█" * filled + "░" * (width - filled)


# ─────────────────────────────────────────────────────────────────────────────
# MLInferencePage
# ─────────────────────────────────────────────────────────────────────────────

class MLInferencePage(QWidget):
    """
    Inference room — ranks library tracks by D1–D4 derivative scores.

    Scores are computed by SongDerivativeModel in a background QThread.
    Hit [Run Scores] (or trigger on_show with auto-run) to populate.
    """

    _MIN_LIBRARY = 4   # SongDerivativeModel minimum

    def __init__(
        self,
        parent: QWidget | None = None,
        ctrl:   object         = None,
    ) -> None:
        super().__init__(parent)
        self._ctrl          = ctrl
        self._scores:  dict[str, dict] = {}   # {path: {d1,d2,d3,d4,target}}
        self._zones:   dict[str, int]  = {}   # {path: zone_id}
        self._playing: str             = ""
        self._worker:  Optional[_ScoreWorker] = None
        self._build()

    # ── layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_header())

        centre = QHBoxLayout()
        centre.setContentsMargins(0, 0, 0, 0)
        centre.setSpacing(0)

        # Left: track list
        left = QWidget()
        left.setStyleSheet(f"background: {BG};")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self._status_lbl = QLabel("  Press [Run Scores] to score your library.")
        self._status_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; padding: 6px 14px; "
            f"background: {CARD2}; border-bottom: 1px solid {BORDER};"
        )
        left_layout.addWidget(self._status_lbl)

        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget {{"
            f"  background: {BG}; border: none; outline: none;"
            f"  font-size: 10px; font-family: Menlo, monospace;"
            f"}}"
            f"QListWidget::item {{"
            f"  color: {FG}; padding: 3px 14px;"
            f"  border-bottom: 1px solid {BORDER};"
            f"}}"
            f"QListWidget::item:selected {{"
            f"  background: {ACC2}; color: {FG};"
            f"}}"
            f"QListWidget::item:hover:!selected {{"
            f"  background: {CARD2};"
            f"}}"
        )
        self._list.currentItemChanged.connect(self._on_selection)
        left_layout.addWidget(self._list, stretch=1)
        centre.addWidget(left, stretch=1)

        # Right: detail panel
        self._detail = _DetailPanel(parent=self)
        centre.addWidget(self._detail)

        root.addLayout(centre, stretch=1)

        self._mini = MiniTransportWidget(ctrl=self._ctrl, parent=self)
        root.addWidget(self._mini)

    def _make_header(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet(f"background: {CARD2}; border-bottom: 1px solid {BORDER};")
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 0, 10, 0)
        row.setSpacing(8)

        title = QLabel("INFERENCE")
        title.setStyleSheet(
            f"color: {ACC}; font-size: 10px; letter-spacing: 3px; "
            "border: none; background: transparent;"
        )
        row.addWidget(title)
        row.addStretch()

        # Route strip
        nav_left = QPushButton("‹")
        nav_left.setFixedWidth(20)
        nav_left.setStyleSheet(
            f"color: {MUTED}; font-size: 13px; padding: 0; "
            "border: none; background: transparent;"
        )
        nav_left.clicked.connect(self._on_nav_prev)
        row.addWidget(nav_left)

        self._route_lbl = self._make_route_label()
        row.addWidget(self._route_lbl)

        nav_right = QPushButton("›")
        nav_right.setFixedWidth(20)
        nav_right.setStyleSheet(
            f"color: {MUTED}; font-size: 13px; padding: 0; "
            "border: none; background: transparent;"
        )
        nav_right.clicked.connect(self._on_nav_next)
        row.addWidget(nav_right)

        row.addSpacing(12)

        self._run_btn = QPushButton("Run Scores")
        self._run_btn.setFixedHeight(22)
        self._run_btn.setStyleSheet(
            f"QPushButton {{"
            f"  color: {FG}; font-size: 9px; letter-spacing: 1px;"
            f"  background: {CARD2}; border: 1px solid {ACC2};"
            f"  padding: 2px 10px; border-radius: 3px;"
            f"}}"
            f"QPushButton:hover {{ background: {ACC2}; border-color: {ACC}; }}"
            f"QPushButton:disabled {{ color: {MUTED}; border-color: {BORDER}; }}"
        )
        self._run_btn.clicked.connect(self._on_run)
        row.addWidget(self._run_btn)

        return bar

    @staticmethod
    def _make_route_label() -> QLabel:
        parts = []
        for i, name in enumerate(_ROUTE):
            if i == _ROUTE_IDX:
                parts.append(f'<span style="color:{ACC}; font-weight:bold;">{name}</span>')
            else:
                parts.append(f'<span style="color:{MUTED};">{name}</span>')
        lbl = QLabel("  ·  ".join(parts))
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setStyleSheet("font-size: 9px; border: none; background: transparent;")
        return lbl

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_nav_prev(self) -> None:
        try:
            self._ctrl.ml_prev_page()
        except AttributeError:
            pass

    def _on_nav_next(self) -> None:
        try:
            self._ctrl.ml_next_page()
        except AttributeError:
            pass

    def _on_run(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        paths = self._library_paths()
        if len(paths) < self._MIN_LIBRARY:
            self._set_status(f"Need ≥ {self._MIN_LIBRARY} tracks. Library has {len(paths)}.")
            return
        self._run_btn.setEnabled(False)
        self._set_status(f"Scoring {len(paths)} tracks…")
        self._worker = _ScoreWorker(paths, parent=self)
        self._worker.finished.connect(self._on_scores_ready)
        self._worker.error.connect(self._on_score_error)
        self._worker.start()

    def _on_scores_ready(self, scores: dict) -> None:
        self._scores = scores
        self._run_btn.setEnabled(True)
        self._set_status(f"Scored {len(scores)} tracks — ranked by D4 ↓")
        self._populate_list()

    def _on_score_error(self, msg: str) -> None:
        self._run_btn.setEnabled(True)
        self._set_status(f"Error: {msg}")

    def _on_selection(self, current: Optional[QListWidgetItem], _prev) -> None:
        if current is None:
            self._detail.clear()
            return
        path = current.data(Qt.ItemDataRole.UserRole)
        if not path:
            self._detail.clear()
            return
        s    = self._scores.get(path, {})
        zone = self._zones.get(path, -1)

        meta: dict = {}
        try:
            meta = self._ctrl.library.get_meta(path) or {}
        except AttributeError:
            pass
        title  = meta.get("title", "") or os.path.splitext(os.path.basename(path))[0]
        artist = meta.get("artist", "")
        self._detail.show_track(title, artist, s, zone)

    # ── list population ───────────────────────────────────────────────────────

    def _populate_list(self) -> None:
        self._list.clear()
        ranked = sorted(
            self._scores.items(),
            key=lambda kv: -(kv[1].get("d4") or 0.0),
        )

        # Preload zones from meta_cache for visual color hints
        self._zones = {}
        try:
            anchored = self._ctrl.meta_cache.get_anchored_annotations("zone_id") or {}
            self._zones = {p: int(ann.get("zone_id", -1)) for p, ann in anchored.items()}
        except Exception:  # noqa: BLE001
            pass

        for path, s in ranked:
            meta: dict = {}
            try:
                meta = self._ctrl.library.get_meta(path) or {}
            except AttributeError:
                pass
            title  = meta.get("title", "") or os.path.splitext(os.path.basename(path))[0]
            artist = meta.get("artist", "")

            d4  = s.get("d4")
            d3  = s.get("d3")
            d1  = s.get("d1")
            d2  = s.get("d2")

            b4 = _score_block(d4, 5)
            b3 = _score_block(d3, 4)
            b1 = _score_block(d1, 4)
            b2 = _score_block(d2, 4)

            d4_str = f"{d4:.3f}" if d4 is not None else "—    "
            label  = (
                f"{d4_str}  {b4}  {b3}  {b1}  {b2}  "
                f"{artist + ' — ' if artist else ''}{title}"
            )

            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, path)

            # Highlight currently playing track
            if path == self._playing:
                item.setForeground(QColor(ACC))

            self._list.addItem(item)

        self._highlight_playing()

    def _highlight_playing(self) -> None:
        """Recolour items to highlight the current track."""
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item is None:
                continue
            path = item.data(Qt.ItemDataRole.UserRole)
            if path == self._playing:
                item.setForeground(QColor(ACC))
            else:
                item.setForeground(QColor(FG))

    # ── helpers ───────────────────────────────────────────────────────────────

    def _library_paths(self) -> list[str]:
        try:
            return list(self._ctrl.library.playlist)
        except AttributeError:
            return []

    def _set_status(self, msg: str) -> None:
        self._status_lbl.setText(f"  {msg}")

    # ── room protocol ─────────────────────────────────────────────────────────

    def on_show(self) -> None:
        # Auto-run if we have no scores yet and the library is big enough
        if not self._scores and len(self._library_paths()) >= self._MIN_LIBRARY:
            self._on_run()

    def on_refresh(self) -> None:
        if self._scores:
            self._populate_list()

    def refresh(self, *args, **kwargs) -> None:
        self.on_refresh()

    def sync_transport(
        self,
        title:    str   = "",
        artist:   str   = "",
        playing:  bool  = False,
        pos:      float = 0.0,
        duration: float = 0.0,
    ) -> None:
        self._mini.sync(title, artist, playing, pos, duration)

    def update_transport(self, *args, **kwargs) -> None:
        self.sync_transport(*args, **kwargs)

    def mark_playing(self, path: Optional[str]) -> None:
        self._playing = path or ""
        self._highlight_playing()

    def set_playing(self, path: Optional[str] = None, **_kwargs) -> None:
        self.mark_playing(path)
