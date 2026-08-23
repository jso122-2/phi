# -*- coding: utf-8 -*-
"""phi.ui.qt.rooms.studio_room — ML Playlist Studio room.

Seed-and-grow arc-controlled playlist builder.

Layout
------
┌─────────────────────────────────────────────────────────────────────┐
│  STUDIO         [▬ FLAT] [↗ RISE] [↘ FALL] [∧ PEAK] [∨ VAL] [∿ WAVE]
├──────────────────────────┬──────────────────────────────────────────┤
│  SEEDS  [+ current]      │  RESULT                                  │
│  ○  Track — Artist       │  1.  Track — Artist  ▬0.82  →0.91       │
│  ○  Track — Artist       │  2.  Track — Artist  ▬0.77  →0.88       │
│  [✕ clear]               │  ...                                     │
│                          │  18/20 annotated  mean arc 0.79          │
│  count: [20 ↑↓]          │                                          │
│  max/artist: [2 ↑↓]      │  [▶ Queue result]                        │
├──────────────────────────┴──────────────────────────────────────────┤
│  [Build Playlist]                                                    │
├─────────────────────────────────────────────────────────────────────┤
│  mini transport                                                      │
└─────────────────────────────────────────────────────────────────────┘

Room protocol: on_show(), on_refresh(), sync_transport(), mark_playing()
"""
from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from phi.config import ACC, ACC2, BG, CARD, CARD2, FG, MUTED, fmt_time
from phi.engine.arc_engine import ArcShape
from phi.engine.playlist_studio import StudioRequest
from phi.engine.studio_plugins import run_plugin

if TYPE_CHECKING:
    from phi.engine.playlist_studio import StudioResult


# ── Arc shape button data ─────────────────────────────────────────────────────

_ARC_BUTTONS = [
    (ArcShape.FLAT,    "▬",  "flat — constant energy"),
    (ArcShape.RISING,  "↗",  "rising — energy builds"),
    (ArcShape.FALLING, "↘",  "falling — energy releases"),
    (ArcShape.PEAK,    "∧",  "peak — builds then drops"),
    (ArcShape.VALLEY,  "∨",  "valley — dips then recovers"),
    (ArcShape.WAVE,    "∿",  "wave — one full oscillation"),
]

_BTN_ACTIVE = (
    f"background: {ACC}; color: {BG}; border: none; "
    "border-radius: 3px; padding: 3px 8px; font-size: 14px;"
)
_BTN_IDLE = (
    f"background: {CARD}; color: {MUTED}; border: 1px solid {CARD2}; "
    "border-radius: 3px; padding: 3px 8px; font-size: 14px;"
)
_BTN_ACTION = (
    f"background: {ACC2}; color: {BG}; border: none; "
    "border-radius: 4px; padding: 6px 18px; font-size: 10px; font-weight: bold;"
)
_BTN_SECONDARY = (
    f"background: transparent; color: {MUTED}; border: 1px solid {CARD2}; "
    "border-radius: 4px; padding: 4px 14px; font-size: 9px;"
)


# ── MLStudioPage ──────────────────────────────────────────────────────────────

class MLStudioPage(QWidget):
    """Playlist Studio room page.

    Args:
        ctrl   : app controller (must have .library, .on_play_path, ._sched)
        parent : optional parent widget
    """

    def __init__(
        self,
        ctrl:   object,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._ctrl          = ctrl
        self._arc_shape     = ArcShape.FLAT
        self._seeds:        list[str] = []
        self._result:       Optional["StudioResult"] = None
        self._build_thread: Optional[threading.Thread] = None
        self._build()

    # ── Layout construction ───────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(6)

        # Header row — title + arc shape toggle row
        hdr_row = QHBoxLayout()
        title = QLabel("Studio")
        title.setStyleSheet(
            f"color: {FG}; font-size: 11px; font-weight: bold; font-family: Menlo, monospace;"
        )
        hdr_row.addWidget(title)
        hdr_row.addStretch()

        # Arc shape buttons
        self._arc_btns: dict[ArcShape, QPushButton] = {}
        for shape, icon, tip in _ARC_BUTTONS:
            btn = QPushButton(icon)
            btn.setToolTip(tip)
            btn.setStyleSheet(_BTN_ACTIVE if shape == self._arc_shape else _BTN_IDLE)
            btn.setFixedWidth(32)
            btn.clicked.connect(lambda _c=False, s=shape: self._on_arc_select(s))
            self._arc_btns[shape] = btn
            hdr_row.addWidget(btn)
        root.addLayout(hdr_row)

        sep = _hline(CARD2)
        root.addWidget(sep)

        # Body splitter: seeds left, result right
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {CARD2}; }}")

        # ── Left pane: seeds + options ─────────────────────────────────────────
        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 8, 0)
        left_l.setSpacing(4)

        seed_hdr = QHBoxLayout()
        seed_lbl = QLabel("Seeds")
        seed_lbl.setStyleSheet(f"color: {FG}; font-size: 10px; font-weight: bold;")
        self._seed_add_btn = QPushButton("+ current")
        self._seed_add_btn.setStyleSheet(_BTN_SECONDARY)
        self._seed_add_btn.setToolTip("Add the currently playing track as a seed")
        self._seed_add_btn.clicked.connect(self._on_add_current)
        seed_hdr.addWidget(seed_lbl)
        seed_hdr.addStretch()
        seed_hdr.addWidget(self._seed_add_btn)
        left_l.addLayout(seed_hdr)

        self._seed_list = QListWidget()
        self._seed_list.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: none; font-size: 9px;"
            f"QListWidget::item:selected {{ background: {ACC2}; }}"
        )
        self._seed_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._seed_list.setFixedHeight(110)
        left_l.addWidget(self._seed_list)

        seed_clear = QPushButton("✕ clear seeds")
        seed_clear.setStyleSheet(
            f"background: transparent; color: {MUTED}; border: none; font-size: 8px; text-align: left;"
        )
        seed_clear.clicked.connect(self._on_clear_seeds)
        left_l.addWidget(seed_clear)

        left_l.addWidget(_hline(CARD2))

        # Options
        opt_lbl = QLabel("Options")
        opt_lbl.setStyleSheet(f"color: {FG}; font-size: 10px; font-weight: bold;")
        left_l.addWidget(opt_lbl)

        def _spin_row(label: str, lo: int, hi: int, default: int) -> tuple[QHBoxLayout, QSpinBox]:
            row   = QHBoxLayout()
            lbl   = QLabel(label)
            lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
            lbl.setFixedWidth(84)
            spin  = QSpinBox()
            spin.setRange(lo, hi)
            spin.setValue(default)
            spin.setFixedWidth(54)
            spin.setStyleSheet(
                f"background: {CARD}; color: {FG}; border: 1px solid {CARD2}; "
                "border-radius: 3px; padding: 2px; font-size: 9px;"
            )
            row.addWidget(lbl)
            row.addWidget(spin)
            row.addStretch()
            return row, spin

        row_count,  self._count_spin  = _spin_row("tracks",       5, 100, 20)
        row_artist, self._artist_spin = _spin_row("max/artist",   1, 10,  2)
        row_genre,  self._genre_spin  = _spin_row("max/genre",    1, 20,  3)
        left_l.addLayout(row_count)
        left_l.addLayout(row_artist)
        left_l.addLayout(row_genre)
        left_l.addStretch()

        splitter.addWidget(left)

        # ── Right pane: result list ─────────────────────────────────────────────
        right = QWidget()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(8, 0, 0, 0)
        right_l.setSpacing(4)

        res_hdr = QHBoxLayout()
        self._result_lbl = QLabel("Result")
        self._result_lbl.setStyleSheet(f"color: {FG}; font-size: 10px; font-weight: bold;")
        self._queue_btn = QPushButton("▶ Queue result")
        self._queue_btn.setStyleSheet(_BTN_SECONDARY)
        self._queue_btn.setEnabled(False)
        self._queue_btn.clicked.connect(self._on_queue_result)
        res_hdr.addWidget(self._result_lbl)
        res_hdr.addStretch()
        res_hdr.addWidget(self._queue_btn)
        right_l.addLayout(res_hdr)

        self._result_list = QListWidget()
        self._result_list.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: none; font-size: 9px;"
            f"QListWidget::item:selected {{ background: {ACC2}; }}"
        )
        self._result_list.itemDoubleClicked.connect(self._on_result_double_click)
        right_l.addWidget(self._result_list, stretch=1)

        self._stats_lbl = QLabel("")
        self._stats_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")
        right_l.addWidget(self._stats_lbl)

        splitter.addWidget(right)
        splitter.setSizes([220, 460])
        root.addWidget(splitter, stretch=1)

        root.addWidget(_hline(CARD2))

        # Build button
        build_row = QHBoxLayout()
        self._build_btn = QPushButton("Build Playlist")
        self._build_btn.setStyleSheet(_BTN_ACTION)
        self._build_btn.clicked.connect(self._on_build)
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")
        build_row.addWidget(self._build_btn)
        build_row.addWidget(self._status_lbl)
        build_row.addStretch()
        root.addLayout(build_row)

    # ── Arc selection ─────────────────────────────────────────────────────────

    def _on_arc_select(self, shape: ArcShape) -> None:
        self._arc_shape = shape
        for s, btn in self._arc_btns.items():
            btn.setStyleSheet(_BTN_ACTIVE if s == shape else _BTN_IDLE)

    # ── Seed management ───────────────────────────────────────────────────────

    def _on_add_current(self) -> None:
        path = getattr(self._ctrl, "current_path", None)
        if not path:
            self._status_lbl.setText("Nothing playing.")
            return
        if path in self._seeds:
            self._status_lbl.setText("Already a seed.")
            return
        if len(self._seeds) >= 5:
            self._status_lbl.setText("Max 5 seeds.")
            return
        self._seeds.append(path)
        lib  = self._ctrl.library  # type: ignore[union-attr]
        meta = lib.get_meta(path) or {}
        name = meta.get("title") or lib.display_name(path)
        artist = meta.get("artist") or ""
        self._seed_list.addItem(f"  ○  {name}" + (f" — {artist}" if artist else ""))
        self._status_lbl.setText(f"Seed added: {name}")

    def _on_clear_seeds(self) -> None:
        self._seeds.clear()
        self._seed_list.clear()
        self._status_lbl.setText("")

    # ── Build ─────────────────────────────────────────────────────────────────

    def _on_build(self) -> None:
        if not self._seeds:
            self._status_lbl.setText("Add at least one seed first.")
            return
        if self._build_thread and self._build_thread.is_alive():
            self._status_lbl.setText("Build already running…")
            return

        self._build_btn.setEnabled(False)
        self._status_lbl.setText("Building…")
        self._result_list.clear()
        self._stats_lbl.setText("")
        self._queue_btn.setEnabled(False)

        request = StudioRequest(
            seeds=list(self._seeds),
            arc_shape=self._arc_shape,
            target_count=self._count_spin.value(),
            max_per_artist=self._artist_spin.value(),
            max_per_genre=self._genre_spin.value(),
        )

        def _worker() -> None:
            try:
                lib   = self._ctrl.library  # type: ignore[union-attr]
                floor = getattr(self._ctrl, "_floor", None)
                result = run_plugin(
                    "playlist_build",
                    {
                        "seeds": list(request.seeds),
                        "arc_shape": request.arc_shape.value,
                        "target_count": request.target_count,
                        "max_per_artist": request.max_per_artist,
                        "max_per_genre": request.max_per_genre,
                    },
                    library=lib,
                    floor=floor,
                )
                # Deliver on main thread
                sched = getattr(self._ctrl, "_sched", None)
                if sched:
                    sched(0, lambda: self._on_build_done(result))
                else:
                    self._on_build_done(result)
            except Exception as exc:
                sched = getattr(self._ctrl, "_sched", None)
                msg   = str(exc)
                if sched:
                    sched(0, lambda: self._on_build_error(msg))
                else:
                    self._on_build_error(msg)

        self._build_thread = threading.Thread(target=_worker, daemon=True)
        self._build_thread.start()

    def _on_build_done(self, result: "StudioResult") -> None:
        self._result = result
        lib  = self._ctrl.library  # type: ignore[union-attr]
        self._result_list.clear()

        for i, path in enumerate(result.tracks):
            meta   = lib.get_meta(path) or {}
            name   = meta.get("title") or lib.display_name(path)
            artist = meta.get("artist") or ""
            arc_s  = result.arc_scores[i] if i < len(result.arc_scores) else 0.0
            tgt    = result.arc_targets[i] if i < len(result.arc_targets) else 0.5
            trans  = result.transition_scores[i - 1] if i > 0 and (i - 1) < len(result.transition_scores) else None

            tag  = f"  arc:{arc_s:.2f}"
            tag += f"  tgt:{tgt:.2f}"
            if trans is not None:
                tag += f"  →{trans:.2f}"

            seed_marker = " [seed]" if path in result.seed_paths else ""
            text = f"  {i + 1:>2}.  {name}" + (f" — {artist}" if artist else "") + seed_marker + tag
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, path)

            # Colour seeds differently
            if path in result.seed_paths:
                item.setForeground(
                    __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(ACC)
                )
            self._result_list.addItem(item)

        self._stats_lbl.setText(
            f"{result.n_annotated} annotated  ·  {result.n_fallback} fallback  ·  "
            f"mean arc {result.mean_arc_score:.3f}  ·  mean transition {result.mean_transition:.3f}"
        )
        self._result_lbl.setText(f"Result  ({len(result.tracks)} tracks)")
        self._queue_btn.setEnabled(bool(result.tracks))
        self._build_btn.setEnabled(True)
        self._status_lbl.setText(f"Done — {len(result.tracks)} tracks built.")

    def _on_build_error(self, msg: str) -> None:
        self._build_btn.setEnabled(True)
        self._status_lbl.setText(f"Error: {msg}")

    # ── Queue / play ──────────────────────────────────────────────────────────

    def _on_queue_result(self) -> None:
        if not self._result or not self._result.tracks:
            return
        ctrl = self._ctrl
        lib  = ctrl.library  # type: ignore[union-attr]
        # Overwrite the library playlist order and jump to first track
        if hasattr(ctrl, "on_play_album"):
            ctrl.on_play_album(self._result.tracks)  # type: ignore[union-attr]
        elif hasattr(ctrl, "on_play_path"):
            ctrl.on_play_path(self._result.tracks[0])  # type: ignore[union-attr]
        if hasattr(ctrl, "tabs"):
            ctrl.tabs.switch_to("tracks")  # type: ignore[union-attr]

    def _on_result_double_click(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and hasattr(self._ctrl, "on_play_path"):
            self._ctrl.on_play_path(path)  # type: ignore[union-attr]
            if hasattr(self._ctrl, "tabs"):
                self._ctrl.tabs.switch_to("tracks")  # type: ignore[union-attr]

    # ── Room protocol ─────────────────────────────────────────────────────────

    def on_show(self) -> None:
        pass

    def on_refresh(self) -> None:
        pass

    def sync_transport(self, *args, **kwargs) -> None:
        pass

    def mark_playing(self, *args, **kwargs) -> None:
        pass


# ── helpers ───────────────────────────────────────────────────────────────────

def _hline(colour: str) -> QWidget:
    w = QWidget()
    w.setFixedHeight(1)
    w.setStyleSheet(f"background: {colour};")
    return w
