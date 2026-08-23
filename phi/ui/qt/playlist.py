# -*- coding: utf-8 -*-
"""phi.ui.qt.playlist — PySide6 track-list panel.

Replaces phi.ui.playlist.PlaylistPanel.

Public API (mirrors PlaylistPanel)
------------------------------------
    search_var              — object with .get() / .set(str)
    refresh(queue, view, queue_pos, library)
    jump_to_current(queue_pos, view)
    flash_status(msg)
    set_watch(active, folder_name="")
    set_sort(key_or_none, rev=False)
    clear_search()
    scroll_up(units=3)
    scroll_down(units=3)
    jump_to_top()
    focus()
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRect, QSize, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from phi.config import ACC, ACC2, BG, CARD, CARD2, FG, MUTED, NOW, SORT_KEYS, fmt_time
from phi.ui.qt.genre_colors import build_genre_map


# ── Genre dot constants ───────────────────────────────────────────────────────

_DOT_ROLE  = Qt.ItemDataRole.UserRole          # hex colour string stored on each item
_DOT_R     = 4                                  # dot radius in px
_DOT_X     = 10                                 # dot centre x from left edge
_DOT_PAD   = _DOT_X + _DOT_R + 6               # left padding reserved for the dot


# ── _GenreDotDelegate ─────────────────────────────────────────────────────────

class _GenreDotDelegate(QStyledItemDelegate):
    """
    Paints a filled colour dot (●) on the left margin of every track row.

    The dot colour is read from ``Qt.ItemDataRole.UserRole`` (a hex string set
    during refresh).  The rest of the row — background, text, selection — is
    delegated to the default painter.
    """

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        # Shift text rect right so it never overlaps the dot
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.rect = option.rect.adjusted(_DOT_PAD, 0, 0, 0)
        super().paint(painter, opt, index)

        hex_c = index.data(_DOT_ROLE)
        if not hex_c:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(hex_c))
        cy = option.rect.y() + option.rect.height() // 2
        painter.drawEllipse(_DOT_X - _DOT_R, cy - _DOT_R, _DOT_R * 2, _DOT_R * 2)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        sh = super().sizeHint(option, index)
        return QSize(sh.width(), max(sh.height(), 28))


# ── _GenreLegend ──────────────────────────────────────────────────────────────

class _GenreLegend(QWidget):
    """
    Horizontally scrollable strip of  ● Genre  chips.

    Call ``set_genres([(label, hex), …])`` after each refresh.
    Clicking a chip emits nothing — it's purely informational for now.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(22)
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setStyleSheet(f"background: transparent; border: none;")

        self._inner = QWidget()
        self._inner.setStyleSheet("background: transparent;")
        self._row = QHBoxLayout(self._inner)
        self._row.setContentsMargins(0, 0, 8, 0)
        self._row.setSpacing(6)

        self._scroll.setWidget(self._inner)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._scroll)

    def set_genres(self, genres: list[tuple[str, str]]) -> None:
        """Update legend chips. ``genres`` = [(label, hex_color), …]."""
        # Clear old chips
        while self._row.count():
            item = self._row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for label, hex_c in genres:
            chip = QLabel(f"● {label}")
            chip.setStyleSheet(
                f"color: {hex_c}; font-size: 8px; "
                f"padding: 1px 0; background: transparent;"
            )
            self._row.addWidget(chip)

        self._row.addStretch()


# ── _SearchVar ────────────────────────────────────────────────────────────────

class _SearchVar:
    """Drop-in for tk.StringVar used by callers via search_var.get()."""

    def __init__(self, edit: QLineEdit) -> None:
        self._edit = edit

    def get(self) -> str:
        return self._edit.text()

    def set(self, val: str) -> None:
        self._edit.setText(val)


class PlaylistWidget(QWidget):
    """
    Contains (top → bottom):
      · ? search bar
      · sort bar
      · track list (QListWidget)
      · toolbar row
      · stats / status strip
    """

    def __init__(self, ctrl: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctrl        = ctrl
        self._view_paths:  list[str]        = []
        self._genre_map:   dict[str, tuple[str, str]] = {}   # path → (hex_color, genre_label)
        self._sort_btns:   dict[str, QPushButton] = {}
        self._pending_refresh: tuple | None = None
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(lambda: self._status_lbl.setText(""))
        self._build()
        self.search_var = _SearchVar(self._search_edit)

    # ── build ──────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 4, 16, 4)
        root.setSpacing(2)

        # ── search bar ────────────────────────────────────────────────────────
        search_row = QHBoxLayout()
        lbl = QLabel("?")
        lbl.setStyleSheet(f"color: {MUTED};")
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("search…")
        self._search_edit.textChanged.connect(
            lambda t: self._ctrl.on_search(t)  # type: ignore[attr-defined]
        )
        clear_btn = QPushButton("✕")
        clear_btn.setFixedWidth(22)
        clear_btn.clicked.connect(self.clear_search)
        search_row.addWidget(lbl)
        search_row.addWidget(self._search_edit, stretch=1)
        search_row.addWidget(clear_btn)

        # ── sort bar ──────────────────────────────────────────────────────────
        sort_row = QHBoxLayout()
        sort_lbl = QLabel("sort:")
        sort_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")
        sort_row.addWidget(sort_lbl)
        for key in SORT_KEYS:
            btn = QPushButton(key.capitalize())
            btn.setStyleSheet(f"font-size: 8px; color: {MUTED}; padding: 2px 6px;")
            btn.clicked.connect(lambda _=False, k=key: self._ctrl.on_sort(k))  # type: ignore[attr-defined]
            sort_row.addWidget(btn)
            self._sort_btns[key] = btn
        default_btn = QPushButton("default")
        default_btn.setStyleSheet(f"font-size: 8px; color: {MUTED}; padding: 2px 6px;")
        default_btn.clicked.connect(self._ctrl.on_sort_clear)  # type: ignore[attr-defined]
        sort_row.addWidget(default_btn)
        sort_row.addStretch()

        # ── genre legend ──────────────────────────────────────────────────────
        self._legend = _GenreLegend(self)

        # ── track list ────────────────────────────────────────────────────────
        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.setStyleSheet(
            f"QListWidget {{ background: {CARD}; alternate-background-color: {CARD2}; }}"
        )
        self._list.setItemDelegate(_GenreDotDelegate(self._list))
        self._list.itemDoubleClicked.connect(self._on_double_click)

        # ── toolbar ───────────────────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.setSpacing(0)

        def _tb(txt: str, cmd, fg: str = FG) -> QPushButton:
            b = QPushButton(txt)
            b.setStyleSheet(f"font-size: 9px; color: {fg}; padding: 4px 6px;")
            b.clicked.connect(cmd)
            return b

        bar.addWidget(_tb("＋ files",   self._ctrl.on_add_files))      # type: ignore[attr-defined]
        bar.addWidget(_tb("＋ folder",  self._ctrl.on_add_folder))     # type: ignore[attr-defined]
        self._watch_btn = _tb("W", self._ctrl.on_toggle_watch, fg=MUTED)  # type: ignore[attr-defined]
        bar.addWidget(self._watch_btn)
        bar.addWidget(_tb("✏ tags",    self._edit_selected_tags))
        bar.addWidget(_tb("▤ save",    self._ctrl.on_save_queue_as_playlist))  # type: ignore[attr-defined]
        bar.addWidget(_tb("sv m3u",    self._ctrl.on_save_m3u))        # type: ignore[attr-defined]
        bar.addWidget(_tb("dir m3u",   self._ctrl.on_load_m3u))        # type: ignore[attr-defined]
        bar.addStretch()
        bar.addWidget(_tb("clear",    self._ctrl.on_clear,  fg=MUTED))  # type: ignore[attr-defined]
        bar.addWidget(_tb("↺ scan",   self._ctrl.on_rescan, fg=MUTED))  # type: ignore[attr-defined]
        bar.addWidget(_tb("dedup",    self._ctrl.on_dedup,  fg=MUTED))  # type: ignore[attr-defined]
        bar.addWidget(_tb("cln",       self._ctrl.on_clean,  fg=MUTED))  # type: ignore[attr-defined]
        bar.addWidget(_tb("✕",        self._remove_selected, fg=MUTED))

        # ── stats strip ───────────────────────────────────────────────────────
        strip = QHBoxLayout()
        jump_btn = QPushButton("⊙")
        jump_btn.setStyleSheet(f"font-size: 9px; color: {MUTED}; padding: 2px 6px;")
        jump_btn.clicked.connect(self._ctrl.on_jump_to_current)  # type: ignore[attr-defined]
        self._stats_lbl    = QLabel("")
        self._status_lbl   = QLabel("")
        self._qpos_lbl     = QLabel("")
        for lbl in (self._stats_lbl, self._status_lbl, self._qpos_lbl):
            lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")
        strip.addWidget(jump_btn)
        strip.addWidget(self._stats_lbl)
        strip.addWidget(self._status_lbl)
        strip.addStretch()
        strip.addWidget(self._qpos_lbl)

        root.addLayout(search_row)
        root.addLayout(sort_row)
        root.addWidget(self._legend)
        root.addWidget(self._list, stretch=1)
        root.addLayout(bar)
        root.addLayout(strip)

    # ── public API ─────────────────────────────────────────────────────────────

    def refresh(
        self,
        queue: list[int],
        view: list[int],
        queue_pos: int,
        library: object,
    ) -> None:
        # Stash args and defer when not visible — avoids rebuilding a list the
        # user cannot see.  show() / showEvent() flushes the pending refresh.
        if not self.isVisible():
            self._pending_refresh = (queue, list(view), queue_pos, library)
            return
        self._pending_refresh = None
        self._do_refresh(queue, view, queue_pos, library)

    def _do_refresh(
        self,
        queue: list[int],
        view: list[int],
        queue_pos: int,
        library: object,
    ) -> None:
        # Build genre colour map for all visible paths in one pass
        view_paths_new = [
            library.playlist[queue[qi]]  # type: ignore[attr-defined]
            for qi in view
            if qi < len(queue) and queue[qi] < len(library.playlist)  # type: ignore[attr-defined]
        ]
        self._genre_map = build_genre_map(view_paths_new, library)

        # Disable repaints for the duration of the rebuild — cuts repaint
        # overhead from O(n) individual layout passes to a single pass at the end.
        self._list.setUpdatesEnabled(False)
        try:
            self._list.clear()
            self._view_paths = []

            for vi, qi in enumerate(view):
                pl_idx: int = queue[qi]  # type: ignore[index]
                path: str   = library.playlist[pl_idx]  # type: ignore[attr-defined]
                meta        = library.get_meta(path)     # type: ignore[attr-defined]
                name        = library.display_name(path)  # type: ignore[attr-defined]
                dur         = meta.get("duration") if meta else None
                dur_s       = f"  {fmt_time(dur)}" if dur else ""
                is_now      = qi == queue_pos
                prefix      = "▶" if is_now else " "

                item = QListWidgetItem(f" {prefix} {qi + 1:>3}.  {name}{dur_s}")
                hex_c, genre_label = self._genre_map.get(path, ("", ""))
                item.setData(_DOT_ROLE, hex_c)
                if genre_label:
                    item.setToolTip(f"{name}  ·  {genre_label}")
                if is_now:
                    item.setForeground(QColor(NOW))
                    item.setBackground(QColor(CARD))
                self._list.addItem(item)
                self._view_paths.append(path)
        finally:
            self._list.setUpdatesEnabled(True)

        self._update_legend(library)

        for vi, qi in enumerate(view):
            if qi == queue_pos:
                self._list.scrollToItem(self._list.item(vi))
                break

        total = len(queue)
        pos   = queue_pos + 1 if queue_pos >= 0 else 0
        self._qpos_lbl.setText(f"{pos} / {total}" if total else "")
        self._stats_lbl.setText(library.stats_str())  # type: ignore[attr-defined]

    def _update_legend(self, library) -> None:
        """Rebuild the genre legend strip from the current genre map."""
        seen: dict[str, str] = {}   # hex → label (first non-empty wins)
        for _path, (hex_c, label) in self._genre_map.items():
            if hex_c not in seen and label:
                seen[hex_c] = label
        chips = sorted(seen.items(), key=lambda kv: kv[1])
        self._legend.set_genres([(label, hex_c) for hex_c, label in chips])

    def showEvent(self, event) -> None:  # type: ignore[override]
        """Flush any refresh that was deferred while the panel was hidden."""
        super().showEvent(event)
        if self._pending_refresh is not None:
            args = self._pending_refresh
            self._pending_refresh = None
            self._do_refresh(*args)

    def jump_to_current(self, queue_pos: int, view: list[int]) -> None:
        for vi, qi in enumerate(view):
            if qi == queue_pos:
                item = self._list.item(vi)
                if item:
                    self._list.scrollToItem(item)
                    self._list.setCurrentItem(item)
                break

    def flash_status(self, msg: str, ms: int = 3_000) -> None:
        self._status_lbl.setText(msg)
        self._flash_timer.stop()
        if msg:
            self._flash_timer.start(ms)

    def set_watch(self, active: bool, folder_name: str = "") -> None:
        color = ACC if active else MUTED
        label = f"W {folder_name}" if (active and folder_name) else "W"
        self._watch_btn.setText(label)
        self._watch_btn.setStyleSheet(
            f"font-size: 9px; color: {color}; padding: 4px 6px;"
        )

    def set_sort(self, key: str | None, rev: bool = False) -> None:
        for k, btn in self._sort_btns.items():
            if k == key:
                color = ACC
            else:
                color = MUTED
            btn.setStyleSheet(f"font-size: 8px; color: {color}; padding: 2px 6px;")

    def clear_search(self) -> None:
        self._search_edit.clear()

    def scroll_up(self, units: int = 3) -> None:
        cur = self._list.currentRow()
        target = max(0, cur - units)
        self._list.setCurrentRow(target)
        item = self._list.item(target)
        if item:
            self._list.scrollToItem(item)

    def scroll_down(self, units: int = 3) -> None:
        cur = self._list.currentRow()
        target = min(self._list.count() - 1, cur + units)
        self._list.setCurrentRow(target)
        item = self._list.item(target)
        if item:
            self._list.scrollToItem(item)

    def jump_to_top(self) -> None:
        if self._list.count():
            self._list.setCurrentRow(0)
            self._list.scrollToTop()

    def focus(self) -> None:
        self._list.setFocus()

    # ── internal ───────────────────────────────────────────────────────────────

    def _on_double_click(self, item: QListWidgetItem) -> None:
        row = self._list.row(item)
        try:
            self._ctrl.on_activate(row)  # type: ignore[attr-defined]
        except Exception:
            import logging, traceback
            logging.getLogger("phi.playlist").warning(
                "on_activate row=%d failed: %s", row, traceback.format_exc()
            )

    def _edit_selected_tags(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._view_paths):
            self._ctrl.on_tag_edit(self._view_paths[row])  # type: ignore[attr-defined]

    def _remove_selected(self) -> None:
        rows = sorted(
            {idx.row() for idx in self._list.selectedIndexes()},
            reverse=True,
        )
        paths = [self._view_paths[r] for r in rows if 0 <= r < len(self._view_paths)]
        if paths:
            self._ctrl.on_remove_tracks(paths)  # type: ignore[attr-defined]
