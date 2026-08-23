# -*- coding: utf-8 -*-
"""phi.ui.qt.rooms.queue_room — live playback queue + CAIRRN dispatch panel.

The magnum opus room.  Three vertical zones:

  ┌─────────────────────────────────────────────────────────────┐
  │  NOW PLAYING  —  album art · title · artist · progress      │  [A]
  ├──────────────────┬──────────────────────────────────────────┤
  │  CAIRRN DISPATCH │  UP NEXT  ──────────── GNN nudge ♻      │  [B]
  │  coherence bar   │  ▶ [locked]  Title · Artist  dur         │
  │  queue depth     │    [locked]  …                           │
  │  action log      │    …  (drag-reorderable)                 │
  │  [Step] [Flush]  │                                          │
  ├──────────────────────────────────────────┴──────────────────┤
  │  mini transport bar                                          │  [C]
  └─────────────────────────────────────────────────────────────┘

Room protocol: on_show(), on_refresh(), sync_transport(), mark_playing().
Refresh hook:  refresh_queue() — call whenever QueueEngine mutates.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, QRect, QSize, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from phi.config import (
    ACC, ACC2, BG, BORDER, CARD, CARD2, FG, GOLD, INDIGO, MUTED, VIOLET,
    fmt_time,
)
from phi.ui.qt.genre_colors import build_genre_map
from phi.ui.qt.rooms._mini_transport import MiniTransportWidget

if TYPE_CHECKING:
    from phi.core.queue   import QueueEngine
    from phi.core.library import Library


# ── geometry constants ────────────────────────────────────────────────────────

_ROW_H       = 34    # px — queue list row height
_ART_SIZE    = 56    # px — now-playing thumbnail square
_CAIRRN_W    = 220   # px — fixed width of the CAIRRN side-panel
_MAX_LOG     = 40    # lines kept in the CAIRRN action log

# ── colour helpers (derived from palette) ─────────────────────────────────────

_NOW_BG      = f"background: {ACC2};"                  # current-track row
_LOCK_BG     = f"background: rgba(92,107,192,0.22);"   # pre-buffered (indigo tint)
_ROW_HOVER   = ACC2

# ── genre dot geometry (shared with PlaylistWidget) ───────────────────────────

_GENRE_ROLE       = Qt.ItemDataRole.UserRole + 1   # hex colour stored on queue items
_GENRE_LABEL_ROLE = Qt.ItemDataRole.UserRole + 2   # genre display label stored on queue items
_DOT_R       = 4
_DOT_X       = 10


# ── art bytes → QPixmap ───────────────────────────────────────────────────────

def _art_bytes_to_pixmap(art_bytes: bytes | None) -> Optional[QPixmap]:
    """Decode raw image bytes (JPEG/PNG/etc) into a QPixmap.  Returns None on failure."""
    if not art_bytes:
        return None
    px = QPixmap()
    return px if px.loadFromData(art_bytes) else None


# ── _DragHandleDelegate ───────────────────────────────────────────────────────

_HANDLE_GLYPH = "⠿"   # braille 6-dot pattern — universally legible grip icon
_HANDLE_W     = 20     # px reserved on the left for the grip column


class _DragHandleDelegate(QStyledItemDelegate):
    """
    Paints a drag-grip glyph (⠿) AND a genre colour dot in the left margin.

    Left margin layout (left → right):
        [4px gap] [grip glyph ~10px] [4px gap] [genre dot 8px] [text …]
    """

    def paint(self, painter, option, index) -> None:
        # Shift text rect past both the handle and the genre dot
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.rect = option.rect.adjusted(_HANDLE_W, 0, 0, 0)
        super().paint(painter, opt, index)

        painter.save()

        # ── drag-grip glyph ───────────────────────────────────────────────────
        grip_rect = QRect(
            option.rect.x() + 4,
            option.rect.y(),
            _HANDLE_W - 4,
            option.rect.height(),
        )
        painter.setFont(QFont("Menlo", 9))
        painter.setPen(QColor(MUTED))
        painter.drawText(
            grip_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            _HANDLE_GLYPH,
        )

        # ── genre colour dot ──────────────────────────────────────────────────
        hex_c = index.data(_GENRE_ROLE)
        if hex_c:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(hex_c))
            cy = option.rect.y() + option.rect.height() // 2
            dx = option.rect.x() + _HANDLE_W + _DOT_X
            painter.drawEllipse(dx - _DOT_R, cy - _DOT_R, _DOT_R * 2, _DOT_R * 2)

        painter.restore()

    def sizeHint(self, option, index) -> QSize:
        sh = super().sizeHint(option, index)
        return QSize(sh.width(), max(sh.height(), _ROW_H))


# ── _QueueListWidget ──────────────────────────────────────────────────────────

class _QueueListWidget(QListWidget):
    """
    Drag-to-reorder queue list.

    Rows are plain text items carrying a ``queue_pos`` role so the controller
    can translate list-row → queue position for the ``swap_view_rows`` call.
    """

    _QUEUE_POS_ROLE = Qt.ItemDataRole.UserRole

    def __init__(self, ctrl: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctrl = ctrl
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSpacing(1)
        self.setStyleSheet(
            f"QListWidget {{"
            f"  background: {CARD}; color: {FG}; border: none;"
            f"  font-size: 10px; outline: none;"
            f"}}"
            f"QListWidget::item {{"
            f"  padding: 6px 10px 6px {_HANDLE_W + 4}px;"
            f"  border-bottom: 1px solid {BORDER};"
            f"}}"
            f"QListWidget::item:selected {{"
            f"  background: {ACC2}; color: {FG};"
            f"}}"
            f"QListWidget::item:hover {{"
            f"  background: rgba(74,56,128,0.35);"
            f"}}"
        )
        self.setItemDelegate(_DragHandleDelegate(self))
        self.itemDoubleClicked.connect(self._on_double_click)

    # ── internal drag-drop reorder ────────────────────────────────────────────

    def dropEvent(self, event) -> None:
        """Wire internal reorder to QueueEngine.swap_view_rows."""
        src_row = self.currentRow()
        super().dropEvent(event)
        dst_row = self.currentRow()
        if src_row != dst_row and hasattr(self._ctrl, "on_swap"):
            self._ctrl.on_swap(src_row, dst_row)

    # ── double-click → play ───────────────────────────────────────────────────

    def _on_double_click(self, item: QListWidgetItem) -> None:
        row = self.row(item)
        if hasattr(self._ctrl, "on_activate"):
            self._ctrl.on_activate(row)


# ── _NowPlayingStrip ──────────────────────────────────────────────────────────

class _NowPlayingStrip(QWidget):
    """
    Zone [A] — compact now-playing header.

    ┌──────────────────────────────────────────────────────────┐
    │ ██  Title                 Artist — Album · year  2:34/4:12│
    │ art ══════════════════════════════════════════════ seek   │
    └──────────────────────────────────────────────────────────┘
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(80)
        self.setStyleSheet(f"background: {CARD2}; border-bottom: 1px solid {BORDER};")
        self._build()

    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 8, 14, 8)
        root.setSpacing(12)

        # Art placeholder
        self._art = QLabel()
        self._art.setFixedSize(_ART_SIZE, _ART_SIZE)
        self._art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._art.setStyleSheet(
            f"background: {CARD}; border: 1px solid {BORDER}; color: {MUTED};"
            f"font-size: 22px;"
        )
        self._art.setText("♪")

        # Text block
        text_col = QWidget()
        text_layout = QVBoxLayout(text_col)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self._title_lbl = QLabel("—")
        self._title_lbl.setStyleSheet(
            f"color: {FG}; font-size: 13px; font-weight: bold;"
        )
        self._title_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(6)
        self._artist_lbl = QLabel("—")
        self._artist_lbl.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        self._album_lbl  = QLabel("")
        self._album_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
        meta_row.addWidget(self._artist_lbl)
        meta_row.addWidget(self._album_lbl)
        meta_row.addStretch()

        self._time_lbl = QLabel("0:00 / 0:00")
        self._time_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
        meta_row.addWidget(self._time_lbl)

        # Progress bar
        self._prog = QProgressBar()
        self._prog.setRange(0, 1000)
        self._prog.setValue(0)
        self._prog.setFixedHeight(3)
        self._prog.setTextVisible(False)
        self._prog.setStyleSheet(
            f"QProgressBar {{ background: {CARD}; border: none; border-radius: 1px; }}"
            f"QProgressBar::chunk {{ background: {ACC}; border-radius: 1px; }}"
        )

        text_layout.addWidget(self._title_lbl)
        text_layout.addLayout(meta_row)
        text_layout.addWidget(self._prog)

        root.addWidget(self._art)
        root.addWidget(text_col, stretch=1)

    # ── public sync ───────────────────────────────────────────────────────────

    def sync(
        self,
        title: str,
        artist: str,
        album: str,
        pos: float,
        duration: float,
        playing: bool,
        art_bytes: bytes | None = None,
    ) -> None:
        self._title_lbl.setText(title or "—")
        self._artist_lbl.setText(artist or "—")
        self._album_lbl.setText(f"· {album}" if album else "")
        if duration > 0:
            self._prog.setValue(int(pos / duration * 1000))
            self._time_lbl.setText(f"{fmt_time(pos)} / {fmt_time(duration)}")
        else:
            self._prog.setValue(0)
            self._time_lbl.setText("—")
        if art_bytes is not None:
            self.set_art_pixmap(_art_bytes_to_pixmap(art_bytes))

    def set_art_pixmap(self, pixmap) -> None:
        """Display album art.  Pass None to reset to the music note glyph."""
        if pixmap is None:
            self._art.setPixmap(None)
            self._art.setText("♪")
        else:
            self._art.setText("")
            self._art.setPixmap(
                pixmap.scaled(
                    _ART_SIZE, _ART_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )


# ── _CAIRRNPanel ──────────────────────────────────────────────────────────────

class _CAIRRNPanel(QWidget):
    """
    Zone [B] right — live CAIRRN dispatcher status.

    Shows:
    • Coherence bar (0–1, coloured by zone: red < 0.45 → amber < 0.57 → green)
    • Queue depth chip
    • Gate status (open / closed)
    • Action log (last N dispatched)
    • [Step] [Flush] buttons
    """

    def __init__(self, ctrl: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctrl = ctrl
        self.setFixedWidth(_CAIRRN_W)
        self.setStyleSheet(
            f"background: {CARD2}; border-right: 1px solid {BORDER};"
        )
        self._log_lines: list[str] = []
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # ── header ────────────────────────────────────────────────────────────
        hdr = QLabel("CAIRRN")
        hdr.setStyleSheet(
            f"color: {ACC}; font-size: 9px; font-weight: bold; letter-spacing: 2px;"
        )

        # ── coherence bar ─────────────────────────────────────────────────────
        coh_lbl = QLabel("coherence")
        coh_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")
        self._coh_bar = QProgressBar()
        self._coh_bar.setRange(0, 1000)
        self._coh_bar.setValue(0)
        self._coh_bar.setFixedHeight(6)
        self._coh_bar.setTextVisible(False)
        self._coh_bar.setStyleSheet(
            f"QProgressBar {{ background: {CARD}; border: none; border-radius: 3px; }}"
            f"QProgressBar::chunk {{ background: {ACC}; border-radius: 3px; }}"
        )
        self._coh_val = QLabel("—")
        self._coh_val.setStyleSheet(f"color: {FG}; font-size: 10px; font-weight: bold;")

        # ── status chips ──────────────────────────────────────────────────────
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self._gate_chip  = QLabel("gate: —")
        self._gate_chip.setStyleSheet(
            f"color: {MUTED}; font-size: 8px; background: {CARD};"
            f"border-radius: 3px; padding: 2px 6px;"
        )
        self._depth_chip = QLabel("depth: 0")
        self._depth_chip.setStyleSheet(
            f"color: {MUTED}; font-size: 8px; background: {CARD};"
            f"border-radius: 3px; padding: 2px 6px;"
        )
        chips.addWidget(self._gate_chip)
        chips.addWidget(self._depth_chip)
        chips.addStretch()

        # ── action log ────────────────────────────────────────────────────────
        log_lbl = QLabel("dispatch log")
        log_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")
        self._log_widget = QListWidget()
        self._log_widget.setStyleSheet(
            f"QListWidget {{ background: {CARD}; color: {MUTED}; border: none;"
            f"  font-size: 8px; font-family: Menlo, 'Courier New', monospace; }}"
            f"QListWidget::item {{ padding: 1px 4px; }}"
        )
        self._log_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self._log_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # ── buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._step_btn = QPushButton("Step")
        self._step_btn.setStyleSheet(
            f"color: {FG}; background: {ACC2}; border: none;"
            f"border-radius: 3px; padding: 4px 10px; font-size: 9px;"
        )
        self._flush_btn = QPushButton("Flush")
        self._flush_btn.setStyleSheet(
            f"color: {MUTED}; background: {CARD}; border: 1px solid {BORDER};"
            f"border-radius: 3px; padding: 4px 10px; font-size: 9px;"
        )
        self._step_btn.clicked.connect(self._on_step)
        self._flush_btn.clicked.connect(self._on_flush)
        btn_row.addWidget(self._step_btn)
        btn_row.addWidget(self._flush_btn)
        btn_row.addStretch()

        # ── assemble ──────────────────────────────────────────────────────────
        root.addWidget(hdr)
        root.addWidget(coh_lbl)
        root.addWidget(self._coh_bar)
        root.addWidget(self._coh_val)
        root.addLayout(chips)
        root.addWidget(log_lbl)
        root.addWidget(self._log_widget, stretch=1)
        root.addLayout(btn_row)

    # ── public sync ───────────────────────────────────────────────────────────

    def sync_dispatcher(self, dispatcher) -> None:
        """Refresh from a live CAIRRNDispatcher (or compatible duck-type)."""
        if dispatcher is None:
            return
        try:
            coh        = float(getattr(dispatcher, "coherence", 0.0))
            gate_open  = bool(getattr(dispatcher, "gate_open", False))
            depth      = int(getattr(dispatcher, "queue_depth", 0))
        except Exception:
            return

        # Coherence bar colour: red → amber → green
        coh_int = int(coh * 1000)
        if coh < 0.45:
            bar_col = "#e05472"    # METER_CRIT
        elif coh < 0.5671:
            bar_col = "#c4a35a"    # GOLD / METER_WARN
        else:
            bar_col = "#3ecf8e"    # METER_OK

        self._coh_bar.setStyleSheet(
            f"QProgressBar {{ background: {CARD}; border: none; border-radius: 3px; }}"
            f"QProgressBar::chunk {{ background: {bar_col}; border-radius: 3px; }}"
        )
        self._coh_bar.setValue(coh_int)
        self._coh_val.setText(f"{coh:.4f}")

        gate_txt   = "open ✓" if gate_open else "closed ✗"
        gate_col   = "#3ecf8e" if gate_open else "#e05472"
        self._gate_chip.setText(f"gate: {gate_txt}")
        self._gate_chip.setStyleSheet(
            f"color: {gate_col}; font-size: 8px; background: {CARD};"
            f"border-radius: 3px; padding: 2px 6px;"
        )
        self._depth_chip.setText(f"depth: {depth}")

        # Pull history snapshot (up to 5 most recent)
        try:
            history = dispatcher.history_snapshot(5)
        except Exception:
            history = []
        for entry in history:
            label = entry if isinstance(entry, str) else str(entry)
            if label not in self._log_lines:
                self._log_lines.append(label)
                if len(self._log_lines) > _MAX_LOG:
                    self._log_lines.pop(0)

        self._log_widget.clear()
        for line in reversed(self._log_lines[-20:]):
            self._log_widget.addItem(line)

    def append_log(self, msg: str) -> None:
        """Append a single line to the action log."""
        self._log_lines.append(msg)
        if len(self._log_lines) > _MAX_LOG:
            self._log_lines.pop(0)
        self._log_widget.insertItem(0, msg)
        while self._log_widget.count() > 20:
            self._log_widget.takeItem(self._log_widget.count() - 1)

    # ── button handlers ───────────────────────────────────────────────────────

    def _on_step(self) -> None:
        dispatcher = getattr(self._ctrl, "cairrn_dispatcher", None)
        if dispatcher is None:
            return
        try:
            result = dispatcher.step()
            self.append_log(f"step → {getattr(result, 'status', result)}")
            self.sync_dispatcher(dispatcher)
        except Exception as exc:
            self.append_log(f"step error: {exc}")

    def _on_flush(self) -> None:
        dispatcher = getattr(self._ctrl, "cairrn_dispatcher", None)
        if dispatcher is None:
            return
        try:
            n = 0
            while getattr(dispatcher, "queue_depth", 0) > 0:
                result = dispatcher.step()
                n += 1
                if n > 64:
                    break
            self.append_log(f"flush → dispatched {n}")
            self.sync_dispatcher(dispatcher)
        except Exception as exc:
            self.append_log(f"flush error: {exc}")


# ── _UpNextHeader ─────────────────────────────────────────────────────────────

class _UpNextHeader(QWidget):
    """Slim header bar above the queue list."""

    def __init__(self, ctrl: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctrl = ctrl
        self.setFixedHeight(32)
        self.setStyleSheet(f"background: {CARD2}; border-bottom: 1px solid {BORDER};")
        self._build()

    def _build(self) -> None:
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 8, 0)
        row.setSpacing(8)

        lbl = QLabel("UP NEXT")
        lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 8px; font-weight: bold; letter-spacing: 2px;"
        )

        self._gnn_lbl = QLabel("")
        self._gnn_lbl.setStyleSheet(f"color: {GOLD}; font-size: 8px;")

        self._count_lbl = QLabel("0 tracks")
        self._count_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")

        _btn_style = (
            f"color: {MUTED}; background: transparent; border: none; font-size: 8px;"
        )

        clr_btn = QPushButton("clear queue")
        clr_btn.setStyleSheet(_btn_style)
        clr_btn.clicked.connect(self._on_clear)

        exp_btn = QPushButton("export ↓")
        exp_btn.setStyleSheet(_btn_style)
        exp_btn.clicked.connect(self._on_export)

        row.addWidget(lbl)
        row.addWidget(self._gnn_lbl)
        row.addStretch()
        row.addWidget(self._count_lbl)
        row.addWidget(exp_btn)
        row.addWidget(clr_btn)

    def set_count(self, total: int, nudge_count: int) -> None:
        self._count_lbl.setText(f"{total} tracks")
        if nudge_count > 0:
            self._gnn_lbl.setText(f"♻ GNN {nudge_count}")
        else:
            self._gnn_lbl.setText("")

    def _on_export(self) -> None:
        """Pop a small menu: save as named playlist or export to M3U file."""
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {CARD}; color: {FG}; border: 1px solid {BORDER};"
            f"  font-size: 9px; padding: 4px 0; }}"
            f"QMenu::item {{ padding: 5px 18px; }}"
            f"QMenu::item:selected {{ background: {ACC2}; color: {FG}; }}"
        )
        act_pl  = menu.addAction("▤  Save as playlist…")
        act_m3u = menu.addAction("↓  Export M3U file…")

        chosen = menu.exec(self.mapToGlobal(self.rect().bottomLeft()))
        if chosen is act_pl:
            fn = getattr(self._ctrl, "on_save_queue_as_playlist", None)
            if fn:
                fn()
        elif chosen is act_m3u:
            fn = getattr(self._ctrl, "on_save_m3u", None)
            if fn:
                fn()

    def _on_clear(self) -> None:
        """Ask the controller to empty the queue (keeps current track)."""
        if not hasattr(self._ctrl, "queue") or not hasattr(self._ctrl, "library"):
            return
        q = self._ctrl.queue
        # Remove everything from pos+1 onward
        if q.pos >= 0:
            q.queue = q.queue[: q.pos + 1]
        else:
            q.queue = []
        if hasattr(self._ctrl, "_rebuild_view"):
            self._ctrl._rebuild_view()


# ── QueueRoom — main widget ───────────────────────────────────────────────────

class QueueRoom(QWidget):
    """
    Live playback queue room — the magnum opus.

    Room protocol
    -------------
        on_show()        — light refresh
        on_refresh()     — full rebuild (called when CAIRRN hub is incoherent)
        sync_transport() — update the mini transport bar + now-playing strip
        mark_playing()   — highlight the currently-playing row
        refresh_queue()  — rebuild the queue list from QueueEngine
    """

    def __init__(self, parent: QWidget | None = None, ctrl: object = None) -> None:
        super().__init__(parent)
        self._ctrl        = ctrl
        self._cache_warm  = False
        self._nudge_count = 0   # incremented by nudge notifications
        self._last_art_path: str | None = None   # guard against redundant pixmap decodes
        self._build()

        # Auto-refresh CAIRRN panel every 2 s when visible
        self._cairrn_timer = QTimer(self)
        self._cairrn_timer.setInterval(2_000)
        self._cairrn_timer.timeout.connect(self._refresh_cairrn)

    # ── layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Zone A — Now Playing strip
        self._now_playing = _NowPlayingStrip(parent=self)
        root.addWidget(self._now_playing)

        # Zone B — body (CAIRRN panel | queue list)
        body = QSplitter(Qt.Orientation.Horizontal)
        body.setHandleWidth(1)
        body.setStyleSheet(f"QSplitter::handle {{ background: {BORDER}; }}")
        root.addWidget(body, stretch=1)

        # Zone B-left: CAIRRN panel
        self._cairrn = _CAIRRNPanel(ctrl=self._ctrl, parent=body)
        body.addWidget(self._cairrn)

        # Zone B-right: header + queue list
        right_container = QWidget()
        right_layout    = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._header = _UpNextHeader(ctrl=self._ctrl, parent=right_container)
        right_layout.addWidget(self._header)

        self._queue_list = _QueueListWidget(ctrl=self._ctrl, parent=right_container)
        right_layout.addWidget(self._queue_list, stretch=1)

        body.addWidget(right_container)

        body.setSizes([_CAIRRN_W, 540])
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        body.setCollapsible(0, True)   # CAIRRN panel can be collapsed

        # Zone C — mini transport
        self._mini = MiniTransportWidget(ctrl=self._ctrl, parent=self)
        root.addWidget(self._mini)

    # ── room protocol ─────────────────────────────────────────────────────────

    def on_show(self) -> None:
        if not self._cache_warm:
            self.on_refresh()
        else:
            self.refresh_queue()
        self._cairrn_timer.start()

    def on_refresh(self) -> None:
        self.refresh_queue()
        self._refresh_cairrn()
        self._cache_warm = True

    def hideEvent(self, event) -> None:
        self._cairrn_timer.stop()
        super().hideEvent(event)

    def sync_transport(
        self,
        title: str,
        artist: str,
        playing: bool,
        pos: float,
        duration: float,
    ) -> None:
        """Update the mini transport bar (room protocol)."""
        self._mini.sync(title, artist, playing, pos, duration)

        # Resolve current track meta for the Now Playing strip
        album: str       = ""
        art_bytes: bytes | None = None

        if self._ctrl is not None:
            cur_idx = getattr(
                getattr(self._ctrl, "queue", None), "current_playlist_idx", -1
            )
            lib = getattr(self._ctrl, "library", None)
            if lib is not None and cur_idx >= 0:
                cur_path = (
                    lib.playlist[cur_idx] if cur_idx < len(lib.playlist) else ""
                )
                if cur_path:
                    meta  = lib.get_meta(cur_path) or {}
                    album = meta.get("album") or ""

                    # Art: only decode when track changes to avoid thrashing
                    if cur_path != self._last_art_path:
                        self._last_art_path = cur_path
                        raw = meta.get("art_bytes")
                        # Fall back to the SQLite cache if the in-memory dict
                        # was populated before art was written back.
                        if not raw:
                            mc = getattr(self._ctrl, "meta_cache", None)
                            if mc is not None:
                                try:
                                    cached = mc.get(cur_path)
                                    raw = (cached or {}).get("art_bytes")
                                except Exception:
                                    raw = None
                        art_bytes = raw or None

        self._now_playing.sync(title, artist, album, pos, duration, playing, art_bytes)

    def mark_playing(self, path: str | None) -> None:
        """Highlight the row that is currently playing."""
        self._highlight_current()

    # ── queue list rebuild ────────────────────────────────────────────────────

    def refresh_queue(self) -> None:
        """
        Rebuild the UP NEXT list from QueueEngine.

        Rows:
          pos      — current track (bold, ACC2 background)
          pos+1    — pre-buffered (INDIGO tint, italic)
          pos+2…   — upcoming (normal)
        """
        if self._ctrl is None:
            return
        q:   "QueueEngine" = getattr(self._ctrl, "queue",   None)
        lib: "Library"     = getattr(self._ctrl, "library", None)
        if q is None or lib is None:
            return

        rows  = q.view if q.view else list(range(len(q.queue)))

        # Build genre colour map for all visible paths in one pass
        visible_paths = [
            lib.playlist[q.queue[qp]]
            for qp in rows
            if qp < len(q.queue) and 0 <= q.queue[qp] < len(lib.playlist)
        ]
        genre_map = build_genre_map(visible_paths, lib)

        self._queue_list.clear()

        total = len(q.view) if q.view else len(q.queue)

        for list_row, queue_pos in enumerate(rows):
            pl_idx   = q.queue[queue_pos] if queue_pos < len(q.queue) else -1
            path     = lib.playlist[pl_idx] if 0 <= pl_idx < len(lib.playlist) else ""
            meta     = lib.get_meta(path) or {} if path else {}
            title    = meta.get("title")   or (os.path.splitext(os.path.basename(path))[0] if path else "—")
            artist   = meta.get("artist")  or ""
            duration = meta.get("duration") or 0.0
            dur_str  = fmt_time(float(duration)) if duration else "—"

            is_current  = (queue_pos == q.pos)
            is_locked   = (queue_pos == q.pos + 1)   # pre-buffered slot

            # Label format: " ▶ Title · Artist  dur" / "   Title · Artist  dur"
            pfx   = "▶ " if is_current else "  "
            body  = f"{title}"
            if artist:
                body += f"  ·  {artist}"
            label = f"{pfx}{body}"

            item = QListWidgetItem(label)
            item.setSizeHint(item.sizeHint().__class__(item.sizeHint().width(), _ROW_H))
            item.setData(_QueueListWidget._QUEUE_POS_ROLE, queue_pos)
            hex_c, genre_label = genre_map.get(path, ("", ""))
            item.setData(_GENRE_ROLE, hex_c)
            item.setData(_GENRE_LABEL_ROLE, genre_label)

            # Styling per slot type
            if is_current:
                item.setForeground(QColor(ACC))
                item.setBackground(QColor(ACC2))
                font = QFont()
                font.setBold(True)
                item.setFont(font)
            elif is_locked:
                item.setForeground(QColor(INDIGO))
                item.setBackground(QColor(CARD2))
                font = QFont()
                font.setItalic(True)
                item.setFont(font)
            else:
                item.setForeground(QColor(FG))

            genre_tip = f"  ·  {genre_label}" if genre_label else ""
            item.setToolTip(f"{title} · {artist} [{dur_str}]{genre_tip}")

            self._queue_list.addItem(item)

        self._header.set_count(total, self._nudge_count)

        # Scroll to current
        if q.pos >= 0:
            self._queue_list.scrollToItem(
                self._queue_list.item(q.pos),
                QAbstractItemView.ScrollHint.PositionAtCenter,
            )

    def _highlight_current(self) -> None:
        """Re-apply colour to the current row without a full rebuild."""
        if self._ctrl is None:
            return
        q = getattr(self._ctrl, "queue", None)
        if q is None:
            return
        for row in range(self._queue_list.count()):
            item     = self._queue_list.item(row)
            qp       = item.data(_QueueListWidget._QUEUE_POS_ROLE) if item else None
            if qp is None:
                continue
            is_cur   = (qp == q.pos)
            is_lock  = (qp == q.pos + 1)
            if is_cur:
                item.setForeground(QColor(ACC))
                item.setBackground(QColor(ACC2))
            elif is_lock:
                item.setForeground(QColor(INDIGO))
                item.setBackground(QColor(CARD2))
            else:
                item.setForeground(QColor(FG))
                item.setBackground(QColor(0, 0, 0, 0))

    # ── CAIRRN panel auto-refresh ─────────────────────────────────────────────

    def _refresh_cairrn(self) -> None:
        dispatcher = getattr(self._ctrl, "cairrn_dispatcher", None)
        self._cairrn.sync_dispatcher(dispatcher)

    # ── nudge notification ────────────────────────────────────────────────────

    def on_gnn_nudge(self, n_reordered: int) -> None:
        """
        Called by the GNN orchestrator after each queue nudge.

        Updates the nudge counter in the header and triggers a queue refresh.
        """
        if n_reordered > 0:
            self._nudge_count += n_reordered
            self.refresh_queue()
