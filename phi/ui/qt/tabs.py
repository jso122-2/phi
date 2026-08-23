# -*- coding: utf-8 -*-
"""phi.ui.qt.tabs — PySide6 tabbed view container.

Replaces phi.ui.tabs.TabbedView (tk.Frame).

Exposes:
    TabbedView   — QTabWidget wrapper (owns all sub-views)
    AlbumView    — two-pane album browser (QWidget)
    ArtistView   — two-pane artist browser (QWidget)
    ModelStatusView — model registry table (QWidget)

Public API (mirrors TabbedView)
---------------------------------
    tracks_view   — PlaylistWidget (backward-compat with app.playlist_panel)
    albums_view   — AlbumView
    artists_view  — ArtistView
    models_view   — ModelStatusView
    enrich_view   — stub (QWidget)
    switch_to(name)
"""
from __future__ import annotations

import os
import threading

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from phi.config import ACC, ACC2, BG, CARD, CARD2, FG, MUTED, fmt_time
from phi.ui.qt.playlist import PlaylistWidget

_TAB_ICONS = {
    "tracks":    "♪",
    "albums":    "◎",
    "artists":   "♫",
    "models":    "◆",
    "discover":  "✦",
    "enrich":    "⊕",
}


# ── AlbumView ─────────────────────────────────────────────────────────────────

class AlbumView(QWidget):
    """
    Two-pane browser: album list left, track list right.
    """

    def __init__(self, ctrl: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctrl          = ctrl
        self._album_data:   list[tuple[str, str, str]] = []
        self._cur_tracks:   list[str] = []
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 8)
        root.setSpacing(4)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Albums")
        title.setStyleSheet(f"color: {FG}; font-size: 11px; font-weight: bold;")
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
        play_all = QPushButton("▶ play all")
        play_all.setStyleSheet(
            f"color: {MUTED}; background: transparent; border: none; font-size: 9px;"
        )
        play_all.clicked.connect(self._play_all)
        hdr.addWidget(title)
        hdr.addWidget(self._count_lbl)
        hdr.addStretch()
        hdr.addWidget(play_all)
        root.addLayout(hdr)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {CARD2}; }}")

        self._album_lb = QListWidget()
        self._album_lb.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: none; font-size: 9px;"
            f"QListWidget::item:selected {{ background: {ACC2}; }}"
        )
        self._album_lb.currentRowChanged.connect(self._on_album_select)
        self._album_lb.itemDoubleClicked.connect(self._on_album_double)
        splitter.addWidget(self._album_lb)

        self._track_lb = QListWidget()
        self._track_lb.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: none; font-size: 9px;"
            f"QListWidget::item:selected {{ background: {ACC2}; }}"
        )
        self._track_lb.itemDoubleClicked.connect(self._on_track_double)
        splitter.addWidget(self._track_lb)

        splitter.setSizes([300, 400])
        root.addWidget(splitter, stretch=1)

        self._info_lbl = QLabel("")
        self._info_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")
        root.addWidget(self._info_lbl)

    # ── public ────────────────────────────────────────────────────────────────

    def on_focus(self) -> None:
        lib = self._ctrl.library  # type: ignore[union-attr]
        self._album_data = lib.albums()
        self._album_lb.clear()
        for artist, album, year in self._album_data:
            yr    = f" ({year})" if year else ""
            n     = lib.album_stats(artist, album)["tracks"]
            self._album_lb.addItem(f"  {artist} — {album}{yr}  ·  {n} tracks")
        self._count_lbl.setText(f"{len(self._album_data)} albums")
        self._track_lb.clear()
        self._info_lbl.setText("")

    def select_album(self, artist: str | None, album: str) -> None:
        for i, (ar, al, _) in enumerate(self._album_data):
            if al == album and (artist is None or ar == artist):
                self._album_lb.setCurrentRow(i)
                return

    # ── events ────────────────────────────────────────────────────────────────

    def _on_album_select(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._album_data):
            return
        artist, album, year = self._album_data[idx]
        lib    = self._ctrl.library  # type: ignore[union-attr]
        tracks = lib.tracks_by_album(artist, album)
        self._cur_tracks = tracks
        self._track_lb.clear()
        for i, path in enumerate(tracks):
            m     = lib.get_meta(path) or {}
            title = m.get("title") or lib.display_name(path)
            dur   = m.get("duration")
            self._track_lb.addItem(
                f"  {i + 1:>2}.  {title}{'  ' + fmt_time(dur) if dur else ''}"
            )
        stats = lib.album_stats(artist, album)
        yr_s  = f"  ·  {year}" if year else ""
        self._info_lbl.setText(
            f"{album}{yr_s}  ·  {stats['tracks']} tracks  ·  {fmt_time(stats['duration'])}"
        )

    def _on_album_double(self, item: QListWidgetItem) -> None:
        idx = self._album_lb.row(item)
        if idx < 0:
            return
        artist, album, _ = self._album_data[idx]
        tracks = self._ctrl.library.tracks_by_album(artist, album)  # type: ignore[union-attr]
        if tracks:
            self._ctrl.on_play_album(tracks)  # type: ignore[union-attr]
            self._ctrl.tabs.switch_to("tracks")  # type: ignore[union-attr]

    def _on_track_double(self, item: QListWidgetItem) -> None:
        row = self._track_lb.row(item)
        if 0 <= row < len(self._cur_tracks):
            idx    = self._album_lb.currentRow()
            artist, album, _ = self._album_data[idx]
            tracks = self._ctrl.library.tracks_by_album(artist, album)  # type: ignore[union-attr]
            self._ctrl.on_play_album(tracks, tracks[row])  # type: ignore[union-attr]
            self._ctrl.tabs.switch_to("tracks")  # type: ignore[union-attr]

    def _play_all(self) -> None:
        if self._album_data:
            artist, album, _ = self._album_data[0]
            tracks = self._ctrl.library.tracks_by_album(artist, album)  # type: ignore[union-attr]
            if tracks:
                self._ctrl.on_play_path(tracks[0])  # type: ignore[union-attr]
                self._ctrl.tabs.switch_to("tracks")  # type: ignore[union-attr]


# ── ArtistView ────────────────────────────────────────────────────────────────

class ArtistView(QWidget):
    """Two-pane artist browser."""

    def __init__(self, ctrl: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctrl        = ctrl
        self._artists:    list[str] = []
        self._cur_tracks: list[str] = []
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 8)
        root.setSpacing(4)

        hdr = QHBoxLayout()
        title = QLabel("Artists")
        title.setStyleSheet(f"color: {FG}; font-size: 11px; font-weight: bold;")
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
        play_all = QPushButton("▶ play all")
        play_all.setStyleSheet(
            f"color: {MUTED}; background: transparent; border: none; font-size: 9px;"
        )
        play_all.clicked.connect(self._play_all)
        hdr.addWidget(title)
        hdr.addWidget(self._count_lbl)
        hdr.addStretch()
        hdr.addWidget(play_all)
        root.addLayout(hdr)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {CARD2}; }}")

        self._artist_lb = QListWidget()
        self._artist_lb.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: none; font-size: 9px;"
            f"QListWidget::item:selected {{ background: {ACC2}; }}"
        )
        self._artist_lb.currentRowChanged.connect(self._on_artist_select)
        self._artist_lb.itemDoubleClicked.connect(self._on_artist_double)
        splitter.addWidget(self._artist_lb)

        self._track_lb = QListWidget()
        self._track_lb.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: none; font-size: 9px;"
            f"QListWidget::item:selected {{ background: {ACC2}; }}"
        )
        self._track_lb.itemDoubleClicked.connect(self._on_track_double)
        splitter.addWidget(self._track_lb)

        splitter.setSizes([260, 440])
        root.addWidget(splitter, stretch=1)

        self._info_lbl = QLabel("")
        self._info_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")
        root.addWidget(self._info_lbl)

    def on_focus(self) -> None:
        lib = self._ctrl.library  # type: ignore[union-attr]
        self._artists = lib.artists()
        self._artist_lb.clear()
        for artist in self._artists:
            stats = lib.artist_stats(artist)
            self._artist_lb.addItem(
                f"  {artist}   ·  {stats['albums']} alb · {stats['tracks']} trk"
            )
        self._count_lbl.setText(f"{len(self._artists)} artists")
        self._track_lb.clear()
        self._info_lbl.setText("")

    def select_artist(self, artist: str) -> None:
        try:
            i = self._artists.index(artist)
            self._artist_lb.setCurrentRow(i)
        except ValueError:
            pass

    def _on_artist_select(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._artists):
            return
        artist = self._artists[idx]
        lib    = self._ctrl.library  # type: ignore[union-attr]
        tracks = lib.tracks_by_artist(artist)
        self._cur_tracks = tracks
        self._track_lb.clear()
        for i, path in enumerate(tracks):
            m     = lib.get_meta(path) or {}
            title = m.get("title") or lib.display_name(path)
            album = m.get("album") or ""
            dur   = m.get("duration")
            self._track_lb.addItem(
                f"  {i + 1:>2}.  {title}"
                f"{'  [' + album + ']' if album else ''}"
                f"{'  ' + fmt_time(dur) if dur else ''}"
            )
        stats = lib.artist_stats(artist)
        self._info_lbl.setText(
            f"{artist}  ·  {stats['albums']} albums  ·  "
            f"{stats['tracks']} tracks  ·  {fmt_time(stats['duration'])}"
        )

    def _on_artist_double(self, item: QListWidgetItem) -> None:
        idx = self._artist_lb.row(item)
        if idx < 0:
            return
        artist = self._artists[idx]
        tracks = self._ctrl.library.tracks_by_artist(artist)  # type: ignore[union-attr]
        if tracks:
            self._ctrl.on_play_path(tracks[0])  # type: ignore[union-attr]
            self._ctrl.tabs.switch_to("tracks")  # type: ignore[union-attr]

    def _on_track_double(self, item: QListWidgetItem) -> None:
        row = self._track_lb.row(item)
        if 0 <= row < len(self._cur_tracks):
            self._ctrl.on_play_path(self._cur_tracks[row])  # type: ignore[union-attr]
            self._ctrl.tabs.switch_to("tracks")  # type: ignore[union-attr]

    def _play_all(self) -> None:
        if self._artists:
            tracks = self._ctrl.library.tracks_by_artist(self._artists[0])  # type: ignore[union-attr]
            if tracks:
                self._ctrl.on_play_path(tracks[0])  # type: ignore[union-attr]
                self._ctrl.tabs.switch_to("tracks")  # type: ignore[union-attr]


# ── ModelStatusView ───────────────────────────────────────────────────────────

class ModelStatusView(QWidget):
    """Model registry status table with run controls."""

    def __init__(self, ctrl: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctrl = ctrl
        self._prog_lbl: QLabel
        self._rows_widget: QWidget
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(6)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Models")
        title.setStyleSheet(f"color: {FG}; font-size: 11px; font-weight: bold;")
        hint  = QLabel("  Register models in phi/models/ to activate")
        hint.setStyleSheet(f"color: {MUTED}; font-size: 8px;")
        run_all = QPushButton("▶ Run all")
        run_all.setStyleSheet(
            f"color: {FG}; background: {ACC2}; border: none; "
            f"border-radius: 3px; padding: 4px 12px; font-size: 9px;"
        )
        run_all.clicked.connect(self._run_all)
        refresh = QPushButton("refresh")
        refresh.setStyleSheet(
            f"color: {MUTED}; background: transparent; border: none; font-size: 9px;"
        )
        refresh.clicked.connect(self.on_focus)
        hdr.addWidget(title)
        hdr.addWidget(hint)
        hdr.addStretch()
        hdr.addWidget(refresh)
        hdr.addWidget(run_all)
        root.addLayout(hdr)

        # Column headers
        col_hdr = QHBoxLayout()
        for txt, w in [("model", 100), ("ver", 50), ("annotated", 80),
                       ("pending", 70), ("status", 80)]:
            lbl = QLabel(txt)
            lbl.setFixedWidth(w)
            lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")
            col_hdr.addWidget(lbl)
        col_hdr.addStretch()
        root.addLayout(col_hdr)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {CARD2};")
        root.addWidget(sep)

        # Model rows container
        self._rows_widget = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(2)
        root.addWidget(self._rows_widget)

        # Progress strip
        sep2 = QWidget()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background: {CARD2};")
        root.addWidget(sep2)
        self._prog_lbl = QLabel("")
        self._prog_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")
        root.addWidget(self._prog_lbl)

        # Description
        desc = QLabel(
            "To activate a model, implement PhiModel in phi/models/ and\n"
            "register it in PhiMainWindow.__init__ via self.models.register(MyModel()).\n\n"
            "Suggested integrations:  librosa (BPM)  ·  Essentia (key/mood)\n"
            "                         CLAP / MuLan (embeddings)  ·  Whisper (lyrics)\n"
            "                         madmom (beat tracking)  ·  any HuggingFace model"
        )
        desc.setStyleSheet(
            f"color: {MUTED}; font-family: Menlo, monospace; font-size: 8px;"
        )
        root.addWidget(desc)
        root.addStretch()

        self.on_focus()

    def on_focus(self) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not hasattr(self._ctrl, "models"):
            return

        statuses = self._ctrl.models.status(self._ctrl.library)  # type: ignore[union-attr]
        if not statuses:
            lbl = QLabel("  No models registered.")
            lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
            self._rows_layout.addWidget(lbl)
            return

        for s in statuses:
            row_w  = QWidget()
            row_l  = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(0)

            for txt, w in [
                (s["name"],           100),
                (s["version"],         50),
                (str(s["annotated"]),  80),
                (str(s["pending"]),    70),
            ]:
                lbl = QLabel(txt)
                lbl.setFixedWidth(w)
                lbl.setStyleSheet(f"color: {FG}; font-size: 9px;")
                row_l.addWidget(lbl)

            status_lbl = QLabel("◎ ready" if s["enabled"] else "○ stub")
            status_lbl.setFixedWidth(80)
            status_lbl.setStyleSheet(
                f"color: {FG if s['enabled'] else MUTED}; font-size: 9px;"
            )
            row_l.addWidget(status_lbl)
            row_l.addStretch()

            run_btn = QPushButton("run")
            run_btn.setStyleSheet(
                f"color: {MUTED}; background: transparent; border: none; font-size: 8px;"
            )
            run_btn.clicked.connect(lambda checked, n=s["name"]: self._run_model(n))
            row_l.addWidget(run_btn)

            self._rows_layout.addWidget(row_w)

    def _run_all(self) -> None:
        if not hasattr(self._ctrl, "models"):
            return
        paths = list(self._ctrl.library.playlist)  # type: ignore[union-attr]
        if not paths:
            self._prog_lbl.setText("Library is empty.")
            return
        self._prog_lbl.setText(f"Running on {len(paths)} tracks…")
        self._ctrl.models.run_batch(  # type: ignore[union-attr]
            paths,
            self._ctrl.library,
            schedule=self._ctrl.after,
            on_progress=self._on_progress,
            on_done=self._on_done,
        )

    def _run_model(self, model_name: str) -> None:
        if not hasattr(self._ctrl, "models"):
            return
        paths = list(self._ctrl.library.playlist)  # type: ignore[union-attr]
        self._prog_lbl.setText(f"Running {model_name} on {len(paths)} tracks…")

        def _worker() -> None:
            models = self._ctrl.models.models  # type: ignore[union-attr]
            m = next((x for x in models if x.name == model_name), None)
            if m is None:
                return
            lib = self._ctrl.library  # type: ignore[union-attr]
            for p in paths:
                meta = lib.get_meta(p) or {}
                if m.can_process(p, meta):
                    r = m.run(p, meta)
                    if r:
                        lib.store_annotation(p, r)
            self._ctrl._sched(0, self._on_done)  # type: ignore[union-attr]

        threading.Thread(target=_worker, daemon=True).start()

    def _on_progress(self, done: int, total: int, path: str) -> None:
        self._prog_lbl.setText(f"{done}/{total}  {os.path.basename(path)}")

    def _on_done(self) -> None:
        self._prog_lbl.setText("Done.")
        self.on_focus()
        if hasattr(self._ctrl, "_flush_annotations"):
            self._ctrl._flush_annotations()  # type: ignore[union-attr]


# ── _NullTabView ──────────────────────────────────────────────────────────────

class _NullTabView(QWidget):
    """Placeholder for sub-views not yet ported (lyrics, enrich, etc.)."""
    def on_focus(self) -> None: pass


# ── TabbedView ────────────────────────────────────────────────────────────────

class TabbedView(QWidget):
    """
    QTabWidget-backed container.

    Exposes:
        self.tracks_view   — PlaylistWidget
        self.albums_view   — AlbumView
        self.artists_view  — ArtistView
        self.models_view   — ModelStatusView
        self.enrich_view   — stub
        self.lyrics_view   — stub
        self.hyphal_view   — stub
        self.genre_view    — stub
        self.playlists_view — stub
        switch_to(name)
    """

    _TAB_KEYS = [
        ("tracks",    "♪  Tracks"),
        ("albums",    "◎  Albums"),
        ("artists",   "♫  Artists"),
        ("models",    "◆  Models"),
        ("enrich",    "⊕  Enrich"),
    ]

    def __init__(self, ctrl: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctrl = ctrl
        self._tabs: dict[str, QWidget] = {}
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._tab_widget = QTabWidget()
        self._tab_widget.setStyleSheet(f"""
            QTabWidget::pane   {{ border: none; background: {BG}; }}
            QTabBar::tab       {{ background: {BG}; color: {MUTED};
                                  padding: 6px 14px; font-size: 10px;
                                  border: none; border-bottom: 2px solid transparent; }}
            QTabBar::tab:selected {{ color: {FG}; border-bottom: 2px solid {ACC}; }}
        """)
        root.addWidget(self._tab_widget)

        self.tracks_view  = PlaylistWidget(ctrl=self._ctrl, parent=self._tab_widget)
        self.albums_view  = AlbumView(ctrl=self._ctrl,   parent=self._tab_widget)
        self.artists_view = ArtistView(ctrl=self._ctrl,  parent=self._tab_widget)
        self.models_view  = ModelStatusView(ctrl=self._ctrl, parent=self._tab_widget)
        self.enrich_view  = _NullTabView(self._tab_widget)
        self.lyrics_view  = _NullTabView(self._tab_widget)
        self.hyphal_view  = _NullTabView(self._tab_widget)
        self.genre_view   = _NullTabView(self._tab_widget)
        self.playlists_view = _NullTabView(self._tab_widget)

        for key, label in self._TAB_KEYS:
            view = getattr(self, f"{key}_view")
            self._tab_widget.addTab(view, label)
            self._tabs[key] = view

        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        # search_var compatibility for app code that reads self.playlist_panel.search_var
        self.search_var = self.tracks_view.search_var

    def _on_tab_changed(self, idx: int) -> None:
        key   = self._TAB_KEYS[idx][0] if idx < len(self._TAB_KEYS) else ""
        view  = self._tab_widget.widget(idx)
        if hasattr(view, "on_focus"):
            view.on_focus()

    def switch_to(self, name: str) -> None:
        for i, (key, _) in enumerate(self._TAB_KEYS):
            if key == name:
                self._tab_widget.setCurrentIndex(i)
                return
