# -*- coding: utf-8 -*-
"""phi.ui.qt.mini_player — compact always-on-top floating player.

Replaces phi.ui.mini_player.MiniPlayer (tk.Toplevel).

A borderless 320×72 QWidget that shows:
  ┌──────────────────────────────────────────┐
  │ [art]  Title                |<  ▶  >|  ✕ │
  │ [art]  Artist               ─────────── │
  └──────────────────────────────────────────┘

Drag by pressing anywhere on the window.
Toggle with ⌘M / toggle_mini_player().

Public API (mirrors MiniPlayer)
---------------------------------
    toggle()
    update_track(path, meta)
    set_playing(playing)
"""
from __future__ import annotations

from io import BytesIO
from typing import Optional

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QFont, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from phi.config import ACC, BG, CARD, FG, MUTED

_W   = 320
_H   = 72
_ART = 52


class MiniPlayer(QWidget):
    """
    Compact floating player.

    Lifecycle
    ---------
    MiniPlayer(ctrl)         — create (shown immediately)
    toggle()                 — show / hide
    update_track(path, meta) — push new track info
    set_playing(playing)     — update play/pause icon
    """

    def __init__(self, ctrl: object) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self._ctrl     = ctrl
        self._visible  = True
        self._drag_pos: Optional[QPoint] = None

        self.setFixedSize(_W, _H)
        self.setStyleSheet(f"background: {CARD}; border-radius: 4px;")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setWindowOpacity(0.94)

        self._build()
        self._center()

        # Push current state
        try:
            idx  = ctrl.queue.current_playlist_idx  # type: ignore[union-attr]
            plib = ctrl.library  # type: ignore[union-attr]
            if 0 <= idx < len(plib.playlist):
                path = plib.playlist[idx]
                meta = plib.get_meta(path)
                self.update_track(path, meta)
                self.set_playing(
                    ctrl.player.is_busy() and not ctrl.player.paused  # type: ignore[union-attr]
                )
        except Exception:
            pass

        self.show()

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Art thumbnail
        self._art_lbl = QLabel()
        self._art_lbl.setFixedSize(_ART, _ART)
        self._art_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._art_lbl.setStyleSheet(
            f"background: {BG}; color: {ACC}; font-size: 18px; font-weight: bold;"
        )
        self._art_lbl.setText("φ")
        layout.addWidget(self._art_lbl)

        # Info + controls
        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        self._title_lbl = QLabel("phi")
        self._title_lbl.setStyleSheet(
            f"color: {FG}; font-size: 11px; font-weight: bold;"
        )
        self._artist_lbl = QLabel("")
        self._artist_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px;")

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(0)

        btn_style = (
            f"color: {MUTED}; font-size: 13px; background: transparent; "
            f"border: none; padding: 0 4px;"
        )
        play_style = (
            f"color: {FG}; font-size: 13px; background: transparent; "
            f"border: none; padding: 0 4px;"
        )

        self._prev_btn = QPushButton("|<")
        self._play_btn = QPushButton("▶")
        self._next_btn = QPushButton(">|")
        self._prev_btn.setStyleSheet(btn_style)
        self._play_btn.setStyleSheet(play_style)
        self._next_btn.setStyleSheet(btn_style)
        self._prev_btn.clicked.connect(self._ctrl.on_prev)  # type: ignore[union-attr]
        self._play_btn.clicked.connect(self._ctrl.on_play_pause)  # type: ignore[union-attr]
        self._next_btn.clicked.connect(self._ctrl.on_next)  # type: ignore[union-attr]

        ctrl_row.addWidget(self._prev_btn)
        ctrl_row.addWidget(self._play_btn)
        ctrl_row.addWidget(self._next_btn)
        ctrl_row.addStretch()

        info_col.addWidget(self._title_lbl)
        info_col.addWidget(self._artist_lbl)
        info_col.addLayout(ctrl_row)
        layout.addLayout(info_col, stretch=1)

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; background: transparent; "
            f"border: none; padding: 2px 6px;"
        )
        close_btn.clicked.connect(self.toggle)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignTop)

    # ── public API ────────────────────────────────────────────────────────────

    def toggle(self) -> None:
        if self._visible:
            self.hide()
        else:
            self.show()
            self.raise_()
        self._visible = not self._visible

    def update_track(self, path: str, meta: dict | None) -> None:
        if not meta:
            self._title_lbl.setText("—")
            self._artist_lbl.setText("")
            self._reset_art()
            return

        title  = meta.get("title")  or ""
        artist = meta.get("artist") or ""
        self._title_lbl.setText(title[:32] + ("…" if len(title) > 32 else ""))
        self._artist_lbl.setText(artist[:32] + ("…" if len(artist) > 32 else ""))

        art_bytes = meta.get("art_bytes")
        if art_bytes:
            try:
                from PIL import Image
                img = Image.open(BytesIO(art_bytes)).resize((_ART, _ART))
                buf = BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)
                px = QPixmap()
                px.loadFromData(buf.read(), "PNG")
                self._art_lbl.setPixmap(px)
                self._art_lbl.setText("")
                return
            except Exception:
                pass
        self._reset_art()

    def set_playing(self, playing: bool) -> None:
        self._play_btn.setText("||" if playing else "▶")

    # ── drag ─────────────────────────────────────────────────────────────────

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e) -> None:
        if self._drag_pos is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e) -> None:
        self._drag_pos = None

    # ── private ───────────────────────────────────────────────────────────────

    def _reset_art(self) -> None:
        self._art_lbl.setPixmap(QPixmap())
        self._art_lbl.setText("φ")

    def _center(self) -> None:
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            self.move(geom.right() - _W - 24, geom.top() + 60)
