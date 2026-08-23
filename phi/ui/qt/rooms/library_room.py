# -*- coding: utf-8 -*-
"""phi.ui.qt.rooms.library_room — Qt full-page library browser with album spines.

Replaces phi.ui.rooms.library_room.LibraryPage (tk.Frame + tk.Canvas).

Layout
------
┌────────────────────────────────────────────────────────────────────┐
│  Library  [search ___________]  [+ Add Folder]   3a · 47al · 612t  │
├──────────┬─────────────────────────────────────────────────────────┤
│ Genre    │  album spines ← scroll →                                │
│          │  ┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐┌──┐                    │
│  All     │  │  ││  ││  ││  ││  ││  ││  ││  │  ← QPainter spines  │
│▼ Electronic  └──┘└──┘└──┘└──┘└──┘└──┘└──┘└──┘                    │
│▼ Hip-Hop ├─────────────────────────────────────────────────────────┤
│          │  Artist — Album  ·  year  ·  N tracks                   │
│          │  1  Track title                          3:24           │
├──────────┴─────────────────────────────────────────────────────────┤
│  mini transport                                                     │
└────────────────────────────────────────────────────────────────────┘

Room protocol: on_show(), on_refresh()
"""
from __future__ import annotations

import hashlib
import os
import re
import threading
from collections import defaultdict
from typing import Any

from PySide6.QtCore import Qt, QRect, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from phi.config import ACC, ACC2, BG, CARD, CARD2, FG, MUTED, fmt_time
from phi.ui.qt.rooms._mini_transport import MiniTransportWidget

# ── spine geometry ────────────────────────────────────────────────────────────
_SPINE_W   = 42
_SPINE_H   = 210
_SPINE_GAP = 4
_BAND_W    = 7

_UNKNOWN_GENRE = "unknown"
_GENRE_SPLIT   = re.compile(r"[;/|,]+")


def _normalise_genre(raw: str) -> str:
    g = raw.lower().strip()
    return g if g else _UNKNOWN_GENRE


def _genres_for_track(meta: dict, ann: dict) -> set[str]:
    out: set[str] = set()
    single = meta.get("genre") or ann.get("genre")
    if single:
        for part in _GENRE_SPLIT.split(str(single)):
            if part.strip():
                out.add(_normalise_genre(part))
    for key in ("mb_genres", "lfm_tags", "discogs_genres"):
        tags = ann.get(key) or []
        if isinstance(tags, str):
            tags = [tags]
        for t in tags:
            if t and str(t).strip():
                out.add(_normalise_genre(str(t)))
    return out or {_UNKNOWN_GENRE}


def _genre_label(genre: str) -> str:
    return genre.replace("-", " ").title() if genre != _UNKNOWN_GENRE else "Unknown"


def _spine_color(artist: str, album: str) -> str:
    """Deterministic dark colour for a spine from artist+album hash."""
    seed = hashlib.md5(f"{artist}:{album}".encode()).digest()
    h = int.from_bytes(seed[:2], "big") % 360
    s = 35 + int.from_bytes(seed[2:4], "big") % 30
    v = 45 + int.from_bytes(seed[4:6], "big") % 25
    from colorsys import hsv_to_rgb
    r, g, b = hsv_to_rgb(h / 360, s / 100, v / 100)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


# ── SpineCanvas ───────────────────────────────────────────────────────────────

class _SpineCanvas(QWidget):
    """Horizontal strip of album spines, drawn via QPainter."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._albums: list[dict] = []   # {artist, album, year, color}
        self._selected = -1
        self._on_select = lambda i: None
        self._on_double = lambda i: None
        self._on_ctrl   = lambda i: None  # ctrl+click callback
        self.setFixedHeight(_SPINE_H + 10)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)

    def set_albums(self, albums: list[dict]) -> None:
        self._albums   = albums
        self._selected = -1
        w = max(self.parent().width() if self.parent() else 600,
                len(albums) * (_SPINE_W + _SPINE_GAP))
        self.setMinimumWidth(w)
        self.update()

    def paintEvent(self, _) -> None:
        if not self._albums:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        font_title = QFont("Menlo", 5)
        font_band  = QFont("Menlo", 4)

        x = 0
        for i, album in enumerate(self._albums):
            color   = QColor(album["color"])
            is_sel  = i == self._selected
            band_c  = QColor(ACC) if is_sel else QColor(color).darker(160)

            # spine body
            p.fillRect(x, 0, _SPINE_W, _SPINE_H, color)
            # left-edge band
            p.fillRect(x, 0, _BAND_W, _SPINE_H, band_c)
            # selection highlight
            if is_sel:
                p.setPen(QPen(QColor(ACC), 1))
                p.drawRect(x, 0, _SPINE_W - 1, _SPINE_H - 1)

            # title text (rotated 90°)
            p.save()
            p.setFont(font_title)
            p.setPen(QColor("#ffffff"))
            p.translate(x + _BAND_W + 3, _SPINE_H - 4)
            p.rotate(-90)
            text = f"{album['artist']}  —  {album['album']}"
            if album.get("year"):
                text += f"  ({album['year']})"
            p.drawText(0, 0, text[:48])

            p.setFont(font_band)
            p.setPen(QColor(ACC2))
            p.drawText(0, 10, album.get("n_tracks_label", ""))
            p.restore()

            x += _SPINE_W + _SPINE_GAP

        p.end()

    def mousePressEvent(self, e) -> None:
        i = e.x() // (_SPINE_W + _SPINE_GAP)
        if 0 <= i < len(self._albums):
            if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self._on_ctrl(i)
            else:
                self._selected = i
                self.update()
                self._on_select(i)

    def mouseDoubleClickEvent(self, e) -> None:
        i = e.x() // (_SPINE_W + _SPINE_GAP)
        if 0 <= i < len(self._albums):
            self._on_double(i)


# ── _LibrarySearchBar ─────────────────────────────────────────────────────────

_SCOPES = ["all", "title", "artist", "album", "year", "genre"]

class _LibrarySearchBar(QWidget):
    """
    Debounced search bar with scope chips and a clear (×) button.

    Layout:  [ 🔍 ______________ × ]  all · title · artist · album · year · genre
    Signals: textChanged fires after _DEBOUNCE_MS of inactivity.
    Public API:
        text()      → current search string (stripped, lower)
        scope()     → active scope string ("all" | "title" | …)
        set_result_count(albums, tracks) → updates the inline result label
    """

    _DEBOUNCE_MS = 160

    def __init__(self, on_change, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on_change = on_change
        self._scope = "all"
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(self._DEBOUNCE_MS)
        self._debounce.timeout.connect(self._fire)
        self._build()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 2)
        root.setSpacing(3)

        # ── row 1: text input ─────────────────────────────────────────────────
        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(4)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText("search library…")
        self._edit.setMinimumWidth(200)
        self._edit.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: 1px solid {ACC2}; "
            f"border-radius: 3px; padding: 3px 8px; font-size: 10px;"
        )
        self._edit.textChanged.connect(self._on_text_changed)

        self._clear_btn = QToolButton()
        self._clear_btn.setText("×")
        self._clear_btn.setFixedSize(20, 20)
        self._clear_btn.setStyleSheet(
            f"color: {MUTED}; background: transparent; border: none; font-size: 13px;"
        )
        self._clear_btn.setVisible(False)
        self._clear_btn.clicked.connect(self._on_clear)

        self._result_lbl = QLabel("")
        self._result_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")

        input_row.addWidget(self._edit, stretch=1)
        input_row.addWidget(self._clear_btn)
        input_row.addWidget(self._result_lbl)
        root.addLayout(input_row)

        # ── row 2: scope chips ────────────────────────────────────────────────
        chips_row = QHBoxLayout()
        chips_row.setContentsMargins(0, 0, 0, 0)
        chips_row.setSpacing(4)

        self._chip_btns: dict[str, QPushButton] = {}
        for scope in _SCOPES:
            btn = QPushButton(scope)
            btn.setCheckable(True)
            btn.setChecked(scope == "all")
            btn.setFixedHeight(16)
            btn.setStyleSheet(self._chip_style(scope == "all"))
            btn.clicked.connect(lambda checked, s=scope: self._on_scope(s))
            chips_row.addWidget(btn)
            self._chip_btns[scope] = btn

        chips_row.addStretch()
        root.addLayout(chips_row)

    @staticmethod
    def _chip_style(active: bool) -> str:
        if active:
            return (
                f"color: {FG}; background: {ACC2}; border: 1px solid {ACC2}; "
                f"border-radius: 3px; padding: 0 6px; font-size: 8px;"
            )
        return (
            f"color: {MUTED}; background: transparent; border: 1px solid {ACC2}; "
            f"border-radius: 3px; padding: 0 6px; font-size: 8px;"
        )

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_text_changed(self, text: str) -> None:
        self._clear_btn.setVisible(bool(text))
        if not text:
            self._result_lbl.setText("")
        self._debounce.start()

    def _on_clear(self) -> None:
        self._edit.clear()
        self._result_lbl.setText("")

    def _on_scope(self, scope: str) -> None:
        self._scope = scope
        for s, btn in self._chip_btns.items():
            btn.setChecked(s == scope)
            btn.setStyleSheet(self._chip_style(s == scope))
        self._fire()

    def _fire(self) -> None:
        self._on_change(self._edit.text().strip().lower(), self._scope)

    # ── public API ────────────────────────────────────────────────────────────

    def text(self) -> str:
        return self._edit.text().strip().lower()

    def scope(self) -> str:
        return self._scope

    def set_result_count(self, albums: int, tracks: int) -> None:
        if albums == 0 and tracks == 0 and not self.text():
            self._result_lbl.setText("")
            return
        self._result_lbl.setText(f"{albums} alb · {tracks} trk")

    def setFocusToEdit(self) -> None:
        self._edit.setFocus()


# ── LibraryPage ───────────────────────────────────────────────────────────────

class LibraryPage(QWidget):
    """
    Full-page library browser.

    Room protocol
    -------------
        on_show()     — called when page becomes visible; fast path
        on_refresh()  — CAIRRN-gated full rebuild
    """

    def __init__(self, parent: QWidget | None = None, ctrl: object = None) -> None:
        super().__init__(parent)
        self._ctrl         = ctrl
        self._cache_warm   = False
        self._genre_filter = ""
        self._albums_all:  list[dict] = []
        self._albums_view: list[dict] = []
        self._cur_tracks:  list[str]  = []
        self._search_results: list[str] = []   # flat track paths from a search hit
        self._build()
        # ⌘F / Ctrl+F focuses the search bar
        from PySide6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("Ctrl+F"), self, self._search_bar.setFocusToEdit)

    # ── layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── header bar ────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setStyleSheet(f"background: {CARD2}; border-bottom: 1px solid {ACC2};")
        hdr_layout = QVBoxLayout(hdr)
        hdr_layout.setContentsMargins(16, 8, 16, 6)
        hdr_layout.setSpacing(4)

        # Title row
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)

        title_lbl = QLabel("Library")
        title_lbl.setStyleSheet(f"color: {ACC}; font-size: 13px; font-weight: bold;")

        add_btn = QPushButton("+ Add Folder")
        add_btn.setStyleSheet(
            f"color: {FG}; background: {CARD}; border: 1px solid {ACC2}; "
            f"border-radius: 3px; padding: 4px 10px; font-size: 10px;"
        )
        add_btn.clicked.connect(self._on_add_folder)

        self._stats_lbl = QLabel("")
        self._stats_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px;")

        title_row.addWidget(title_lbl)
        title_row.addStretch()
        title_row.addWidget(self._stats_lbl)
        title_row.addWidget(add_btn)
        hdr_layout.addLayout(title_row)

        # Search bar (debounced, scoped)
        self._search_bar = _LibrarySearchBar(on_change=self._on_search, parent=hdr)
        hdr_layout.addWidget(self._search_bar)

        root.addWidget(hdr)

        # ── main splitter: genre sidebar | right pane ─────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {CARD2}; }}")
        root.addWidget(splitter, stretch=1)

        # Left: genre tree
        self._genre_tree = QTreeWidget()
        self._genre_tree.setHeaderHidden(True)
        self._genre_tree.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: none; font-size: 9px;"
            f"QTreeWidget::item:selected {{ background: {ACC2}; }}"
        )
        self._genre_tree.setFixedWidth(140)
        self._genre_tree.itemClicked.connect(self._on_genre_click)
        splitter.addWidget(self._genre_tree)

        # Right pane (spine scroll + track list)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Spine scroll area
        self._spine_scroll = QScrollArea()
        self._spine_scroll.setFixedHeight(_SPINE_H + 16)
        self._spine_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self._spine_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._spine_scroll.setWidgetResizable(False)
        self._spine_scroll.setStyleSheet(f"background: {BG}; border: none;")

        self._spine_canvas = _SpineCanvas()
        self._spine_canvas._on_select = self._on_spine_select
        self._spine_canvas._on_double = self._on_spine_double
        self._spine_canvas._on_ctrl   = self._on_spine_ctrl
        self._spine_scroll.setWidget(self._spine_canvas)
        right_layout.addWidget(self._spine_scroll)

        # Album info strip
        self._album_info = QLabel("")
        self._album_info.setStyleSheet(
            f"color: {MUTED}; font-size: 8px; padding: 2px 12px; background: {CARD2};"
        )
        right_layout.addWidget(self._album_info)

        # Track list
        self._track_list = QListWidget()
        self._track_list.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: none; font-size: 9px;"
            f"QListWidget::item:selected {{ background: {ACC2}; }}"
        )
        self._track_list.setAlternatingRowColors(False)
        self._track_list.itemDoubleClicked.connect(self._on_track_double)
        self._track_list.itemClicked.connect(self._on_track_clicked)
        right_layout.addWidget(self._track_list, stretch=1)

        splitter.addWidget(right)
        splitter.setSizes([140, 600])

        # ── mini transport ────────────────────────────────────────────────────
        self._mini = MiniTransportWidget(ctrl=self._ctrl)
        root.addWidget(self._mini)

    # ── tabs embedding ────────────────────────────────────────────────────────

    def embed_tabs(self, tabs_widget: QWidget) -> None:
        """Reparent the TabbedView into this page as the default (full-page) view.

        Creates an internal QStackedWidget:
          index 0 — TabbedView (tracks/albums/artists/…)  ← default
          index 1 — deep browser (genre tree + spine canvas + track list)

        Cmd+/ calls toggle_deep() to flip between them.
        Called once from PhiMainWindow.__init__ after LibraryPage is created.
        """
        root = self.layout()  # QVBoxLayout: [header, h_splitter, mini]

        # Pull the deep browser out of the root layout for reparenting
        h_splitter = root.itemAt(1).widget()
        root.removeWidget(h_splitter)

        self._stack = QStackedWidget()
        self._stack.addWidget(tabs_widget)   # index 0: song/album selector (default)
        self._stack.addWidget(h_splitter)    # index 1: spine + genre browser
        self._stack.setCurrentIndex(0)

        # Re-insert between the header and the mini transport
        root.insertWidget(1, self._stack, stretch=1)
        self._tabs_view = tabs_widget

    def toggle_deep(self) -> None:
        """Toggle between the full-page tab list (index 0) and the deep browser (index 1)."""
        if not hasattr(self, "_stack"):
            return
        new_idx = 1 - self._stack.currentIndex()
        self._stack.setCurrentIndex(new_idx)
        if new_idx == 1:
            # Rebuild if the deep browser hasn't been populated yet
            self.on_refresh()

    # ── room protocol ─────────────────────────────────────────────────────────

    def on_show(self) -> None:
        # Always land on the tab list view when navigating to the library page
        if hasattr(self, "_stack"):
            self._stack.setCurrentIndex(0)
        if not self._cache_warm:
            QTimer.singleShot(0, self.on_refresh)

    def on_refresh(self) -> None:
        self._build_genre_tree()
        self._load_albums("")
        self._update_stats()
        self._cache_warm = True

    def sync_transport(
        self,
        title: str,
        artist: str,
        playing: bool,
        pos: float,
        duration: float,
    ) -> None:
        self._mini.sync(title, artist, playing, pos, duration)

    def mark_playing(self, path: str | None) -> None:
        pass

    # ── genre sidebar ─────────────────────────────────────────────────────────

    def _build_genre_tree(self) -> None:
        lib = self._ctrl.library  # type: ignore[union-attr]
        self._genre_tree.clear()

        genre_artists: dict[str, set[str]] = defaultdict(set)
        for path in lib.playlist:
            meta = lib.get_meta(path) or {}
            ann  = lib.get_annotation(path) or {}
            for g in _genres_for_track(meta, ann):
                artist = (meta.get("artist") or "Unknown").strip()
                genre_artists[g].add(artist)

        all_item = QTreeWidgetItem(["All"])
        all_item.setData(0, Qt.ItemDataRole.UserRole, "")
        self._genre_tree.addTopLevelItem(all_item)

        for genre in sorted(genre_artists):
            parent = QTreeWidgetItem([_genre_label(genre)])
            parent.setData(0, Qt.ItemDataRole.UserRole, genre)
            parent.setForeground(0, QColor(FG))
            for artist in sorted(genre_artists[genre]):
                child = QTreeWidgetItem([f"  {artist}"])
                child.setData(0, Qt.ItemDataRole.UserRole, f"artist:{genre}:{artist}")
                child.setForeground(0, QColor(MUTED))
                parent.addChild(child)
            self._genre_tree.addTopLevelItem(parent)

        all_item.setSelected(True)

    def _on_genre_click(self, item: QTreeWidgetItem, _col: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole) or ""
        if data.startswith("artist:"):
            _, genre, artist = data.split(":", 2)
            self._load_albums(genre, artist_filter=artist)
        else:
            self._load_albums(data)

    # ── album spines ──────────────────────────────────────────────────────────

    def _load_albums(self, genre_filter: str = "", artist_filter: str = "") -> None:
        lib = self._ctrl.library  # type: ignore[union-attr]
        self._genre_filter = genre_filter

        all_albums = lib.albums()
        filtered: list[dict] = []

        for artist, album, year in all_albums:
            if artist_filter and artist != artist_filter:
                continue
            if genre_filter:
                tracks = lib.tracks_by_album(artist, album)
                match  = False
                for p in tracks:
                    m = lib.get_meta(p) or {}
                    a = lib.get_annotation(p) or {}
                    if genre_filter in _genres_for_track(m, a):
                        match = True
                        break
                if not match:
                    continue
            n = lib.album_stats(artist, album)["tracks"]
            filtered.append({
                "artist":        artist,
                "album":         album,
                "year":          year,
                "color":         _spine_color(artist, album),
                "n_tracks_label": f"{n}t",
            })

        self._albums_view = filtered
        # Keep a full (unfiltered) snapshot so search always has a complete base
        if not genre_filter and not artist_filter:
            self._albums_all = filtered
        self._spine_canvas.set_albums(filtered)
        self._track_list.clear()
        self._album_info.setText("")
        self._cur_tracks = []

    def _on_spine_select(self, idx: int) -> None:
        if idx >= len(self._albums_view):
            return
        a = self._albums_view[idx]
        lib    = self._ctrl.library  # type: ignore[union-attr]
        tracks = lib.tracks_by_album(a["artist"], a["album"])
        self._cur_tracks = tracks

        self._track_list.clear()
        for i, path in enumerate(tracks):
            m     = lib.get_meta(path) or {}
            title = m.get("title") or lib.display_name(path)
            dur   = m.get("duration")
            dur_s = f"  {fmt_time(dur)}" if dur else ""
            item  = QListWidgetItem(f"  {i + 1:>2}.  {title}{dur_s}")
            self._track_list.addItem(item)

        stats  = lib.album_stats(a["artist"], a["album"])
        yr_s   = f"  ·  {a['year']}" if a.get("year") else ""
        self._album_info.setText(
            f"{a['artist']} — {a['album']}{yr_s}  ·  "
            f"{stats['tracks']} tracks  ·  {fmt_time(stats['duration'])}"
        )

    def _on_spine_double(self, idx: int) -> None:
        if idx >= len(self._albums_view):
            return
        a      = self._albums_view[idx]
        lib    = self._ctrl.library  # type: ignore[union-attr]
        tracks = lib.tracks_by_album(a["artist"], a["album"])
        if tracks:
            self._ctrl.on_play_album(tracks)  # type: ignore[union-attr]

    def _ctrl_menu(self) -> QMenu:
        """Shared styled QMenu for ctrl+click dropdowns."""
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {CARD2}; color: {FG}; border: 1px solid {ACC2}; "
            f"font-size: 9px; padding: 2px; }}"
            f"QMenu::item {{ padding: 5px 18px 5px 10px; }}"
            f"QMenu::item:selected {{ background: {ACC2}; }}"
            f"QMenu::separator {{ height: 1px; background: {ACC2}; margin: 2px 6px; }}"
        )
        return menu

    def _on_spine_ctrl(self, idx: int) -> None:
        """Ctrl+click on an album spine — queue dropdown."""
        if idx >= len(self._albums_view):
            return
        a      = self._albums_view[idx]
        lib    = self._ctrl.library  # type: ignore[union-attr]
        tracks = lib.tracks_by_album(a["artist"], a["album"])
        if not tracks:
            return

        menu      = self._ctrl_menu()
        act_queue = menu.addAction(f"+ Queue album  ({len(tracks)} tracks)")
        act_next  = menu.addAction("⤴ Play next")
        menu.addSeparator()
        act_pl    = menu.addAction("▤ Add to playlist…")
        act_pl.setEnabled(False)  # TODO: wire playlist picker

        chosen = menu.exec(QCursor.pos())
        if chosen == act_queue:
            self._ctrl.on_queue_append_many(tracks)  # type: ignore[union-attr]
        elif chosen == act_next:
            self._ctrl.on_play_next_many(tracks)     # type: ignore[union-attr]

    def _on_track_double(self, item: QListWidgetItem) -> None:
        row = self._track_list.row(item)
        if 0 <= row < len(self._cur_tracks):
            lib    = self._ctrl.library  # type: ignore[union-attr]
            spine  = self._spine_canvas._selected
            if spine >= 0 and spine < len(self._albums_view):
                a      = self._albums_view[spine]
                tracks = lib.tracks_by_album(a["artist"], a["album"])
                self._ctrl.on_play_album(tracks, tracks[row])  # type: ignore[union-attr]

    def _on_track_clicked(self, item: QListWidgetItem) -> None:
        """Single-click on a track row — opens queue dropdown on ctrl+click."""
        if not (QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier):
            return
        row = self._track_list.row(item)
        if row < 0 or row >= len(self._cur_tracks):
            return
        path = self._cur_tracks[row]
        lib  = self._ctrl.library  # type: ignore[union-attr]
        m    = lib.get_meta(path) or {}
        title = m.get("title") or lib.display_name(path)

        menu      = self._ctrl_menu()
        act_queue = menu.addAction(f'+ Queue  \u201c{title}\u201d')
        act_next  = menu.addAction("⤴ Play next")
        menu.addSeparator()
        act_pl    = menu.addAction("▤ Add to playlist…")
        act_pl.setEnabled(False)  # TODO: wire playlist picker

        chosen = menu.exec(QCursor.pos())
        if chosen == act_queue:
            self._ctrl.on_queue_append(path)   # type: ignore[union-attr]
        elif chosen == act_next:
            self._ctrl.on_play_next_path(path) # type: ignore[union-attr]

    # ── search & add ─────────────────────────────────────────────────────────

    def _on_search(self, text: str, scope: str = "all") -> None:
        """
        Scoped, multi-field search over the library.

        Scope values
        ------------
        all    — title + artist + album + year + genre (OR across all fields)
        title  — track title only (triggers track scan)
        artist — artist name
        album  — album title
        year   — release year (string prefix match)
        genre  — genre tag

        Results
        -------
        Spine canvas is filtered to matching albums.
        Track list is populated with all tracks that match (for title/all scope).
        In tabs mode the tracks tab search is also forwarded.
        """
        if not text:
            self._load_albums(self._genre_filter)
            self._search_bar.set_result_count(0, 0)
            # Clear forwarded search
            self._forward_search("")
            return

        lib = self._ctrl.library  # type: ignore[union-attr]
        matched_albums: list[dict] = []
        matched_tracks: list[str] = []

        base = self._albums_all if self._albums_all else self._albums_view

        for album_d in base:
            artist = album_d["artist"].lower()
            album  = album_d["album"].lower()
            year   = str(album_d.get("year") or "").lower()

            album_hit = False

            if scope in ("all", "artist"):
                if text in artist:
                    album_hit = True
            if scope in ("all", "album"):
                if text in album:
                    album_hit = True
            if scope in ("all", "year"):
                if year.startswith(text):
                    album_hit = True

            # Genre and title require scanning tracks
            if not album_hit and scope in ("all", "genre", "title"):
                tracks = lib.tracks_by_album(album_d["artist"], album_d["album"])
                for p in tracks:
                    meta = lib.get_meta(p) or {}
                    ann  = lib.get_annotation(p) or {}
                    if scope in ("all", "title"):
                        t_title = (meta.get("title") or "").lower()
                        if text in t_title:
                            album_hit = True
                            matched_tracks.append(p)
                    if scope in ("all", "genre"):
                        for g in _genres_for_track(meta, ann):
                            if text in g.lower():
                                album_hit = True

            if album_hit:
                matched_albums.append(album_d)

        # For artist/album/year/genre scope also gather all matching tracks
        if scope not in ("all", "title") and matched_albums:
            for album_d in matched_albums:
                matched_tracks.extend(
                    lib.tracks_by_album(album_d["artist"], album_d["album"])
                )

        self._albums_view   = matched_albums
        self._search_results = matched_tracks
        self._spine_canvas.set_albums(matched_albums)

        # Show match list in the track panel when there are explicit track hits
        if matched_tracks:
            self._show_search_results(matched_tracks)
        else:
            self._track_list.clear()
            self._album_info.setText(f"  {len(matched_albums)} album(s) matched")
            self._cur_tracks = []

        self._search_bar.set_result_count(len(matched_albums), len(matched_tracks))

        # Forward to the tabs search so the Tracks tab stays in sync
        self._forward_search(text if scope in ("all", "title", "artist") else "")

    def _show_search_results(self, paths: list[str]) -> None:
        """Populate the track list with a flat list of search-result tracks."""
        lib = self._ctrl.library  # type: ignore[union-attr]
        self._track_list.clear()
        self._cur_tracks = paths
        for i, path in enumerate(paths[:500]):     # cap at 500 for performance
            meta   = lib.get_meta(path) or {}
            title  = meta.get("title") or lib.display_name(path)
            artist = meta.get("artist") or ""
            dur    = meta.get("duration")
            dur_s  = f"  {fmt_time(dur)}" if dur else ""
            suffix = f"  ·  {artist}" if artist else ""
            self._track_list.addItem(f"  {i + 1:>3}.  {title}{suffix}{dur_s}")
        self._album_info.setText(
            f"  Search results — {len(paths)} track(s) matched"
            + (f"  (showing first 500)" if len(paths) > 500 else "")
        )

    def _forward_search(self, text: str) -> None:
        """Forward a search string to the Tracks tab's search bar (if visible)."""
        try:
            self._ctrl.playlist_panel.search_var.set(text)  # type: ignore[union-attr]
            if hasattr(self._ctrl, "_rebuild_view"):
                self._ctrl._rebuild_view(text or None)       # type: ignore[union-attr]
        except Exception:
            pass

    def _on_add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Choose music folder", os.path.expanduser("~")
        )
        if folder:
            self._ctrl.on_add_folder_path(folder)  # type: ignore[union-attr]

    def _update_stats(self) -> None:
        lib = self._ctrl.library  # type: ignore[union-attr]
        artists = len(set(ar for ar, _al, _yr in lib.albums()))
        albums  = len(lib.albums())
        tracks  = lib.size
        self._stats_lbl.setText(
            f"{artists} artists  ·  {albums} albums  ·  {tracks} tracks"
        )
