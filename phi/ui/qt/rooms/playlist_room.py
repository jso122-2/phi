# -*- coding: utf-8 -*-
"""phi.ui.qt.rooms.playlist_room — Qt drag-and-build playlist studio.

Three-pane layout:
  Left   — Spotify / saved playlists sidebar (from PlaylistStore)
  Middle — library browser (filterable track list)
  Right  — working playlist (reorderable, save as M3U)

Spotify sidebar features:
  • Lists all playlists from PlaylistStore (Spotify-origin first)
  • Click → loads into working playlist
  • ▶ Play → calls on_play_album() directly
  • ↺ Sync → triggers SpotifySync in a background thread (with progress)

Room protocol: on_show(), on_refresh(), sync_transport()
"""
from __future__ import annotations

import os
import threading
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from phi.config import ACC, ACC2, BG, CARD, CARD2, FG, GOLD, MUTED
from phi.ui.qt.rooms._mini_transport import MiniTransportWidget


# ── _SpotifyPlaylistSidebar ───────────────────────────────────────────────────

class _SpotifyPlaylistSidebar(QWidget):
    """
    Left panel: lists all saved/Spotify playlists from PlaylistStore.

    Shows: playlist name, track count, Spotify badge (if Spotify-origin).
    Actions:
      • Single click  → load tracks into working playlist (right pane)
      • Double click  → load + play immediately
      • ↺ Sync button → full Spotify sync (SpotifySync.run) in background thread
    """

    _PL_ID_ROLE = Qt.ItemDataRole.UserRole   # PlaylistInfo.id stored on each item

    def __init__(self, ctrl: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctrl        = ctrl
        self._on_load:    Optional[callable] = None   # callback(paths: list[str])
        self._on_play:    Optional[callable] = None   # callback(paths: list[str])
        self._sync_thread: Optional[threading.Thread] = None
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── header ────────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setStyleSheet(f"background: {CARD2}; border-bottom: 1px solid {ACC2};")
        hdr_l = QHBoxLayout(hdr)
        hdr_l.setContentsMargins(10, 6, 6, 6)
        hdr_l.setSpacing(4)

        title = QLabel("Playlists")
        title.setStyleSheet(
            f"color: {ACC}; font-size: 10px; font-weight: bold; letter-spacing: 1px;"
        )
        hdr_l.addWidget(title)
        hdr_l.addStretch()

        self._sync_btn = QPushButton("↺ Sync")
        self._sync_btn.setToolTip("Sync all playlists from Spotify")
        self._sync_btn.setStyleSheet(
            f"color: {GOLD}; background: transparent; border: 1px solid {GOLD}; "
            f"border-radius: 3px; padding: 2px 8px; font-size: 8px;"
        )
        self._sync_btn.clicked.connect(self._on_sync)
        hdr_l.addWidget(self._sync_btn)

        root.addWidget(hdr)

        # ── status label ──────────────────────────────────────────────────────
        self._status = QLabel("")
        self._status.setStyleSheet(
            f"color: {MUTED}; font-size: 7px; padding: 2px 10px; background: {CARD2};"
        )
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        # ── playlist list ─────────────────────────────────────────────────────
        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget {{ background: {CARD}; color: {FG}; border: none; font-size: 9px; }}"
            f"QListWidget::item {{ padding: 4px 10px; border-bottom: 1px solid {CARD2}; }}"
            f"QListWidget::item:selected {{ background: {ACC2}; color: {FG}; }}"
        )
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.itemClicked.connect(self._on_click)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        root.addWidget(self._list, stretch=1)

        # ── action buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(6, 4, 6, 4)
        btn_row.setSpacing(4)

        self._play_btn = QPushButton("▶ Play")
        self._play_btn.setEnabled(False)
        self._play_btn.setStyleSheet(
            f"color: {FG}; background: {ACC2}; border: none; "
            f"border-radius: 3px; padding: 4px 10px; font-size: 9px;"
        )
        self._play_btn.clicked.connect(self._on_play_btn)

        self._load_btn = QPushButton("Load →")
        self._load_btn.setEnabled(False)
        self._load_btn.setStyleSheet(
            f"color: {MUTED}; background: transparent; border: 1px solid {CARD2}; "
            f"border-radius: 3px; padding: 4px 10px; font-size: 9px;"
        )
        self._load_btn.clicked.connect(self._on_load_btn)

        btn_row.addWidget(self._play_btn)
        btn_row.addWidget(self._load_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

    # ── public API ────────────────────────────────────────────────────────────

    def set_callbacks(
        self,
        on_load: callable,
        on_play: callable,
    ) -> None:
        self._on_load = on_load
        self._on_play = on_play

    def refresh(self) -> None:
        """Reload playlist list from PlaylistStore."""
        store = getattr(self._ctrl, "playlist_store", None)
        if store is None:
            return
        self._list.clear()
        try:
            playlists = store.all()
        except Exception:
            return

        # Spotify-origin first, then local playlists, both alphabetical
        spotify_pls = [p for p in playlists if p.spotify_id]
        local_pls   = [p for p in playlists if not p.spotify_id]

        for group, prefix in [(spotify_pls, "♫ "), (local_pls, "▤ ")]:
            for pl in group:
                label = f"{prefix}{pl.name}  ·  {pl.track_count}"
                if pl.owner:
                    label += f"  {pl.owner}"
                item = QListWidgetItem(label)
                item.setData(self._PL_ID_ROLE, pl.id)
                if pl.spotify_id:
                    item.setForeground(
                        __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(GOLD)
                    )
                self._list.addItem(item)

        total = len(playlists)
        sp_count = len(spotify_pls)
        self._status.setText(
            f"{total} playlist{'s' if total != 1 else ''}  ·  {sp_count} from Spotify"
        )

    # ── private ───────────────────────────────────────────────────────────────

    def _selected_paths(self) -> list[str]:
        """Return track paths for the currently selected playlist."""
        item = self._list.currentItem()
        if not item:
            return []
        pl_id = item.data(self._PL_ID_ROLE)
        if pl_id is None:
            return []
        store = getattr(self._ctrl, "playlist_store", None)
        if store is None:
            return []
        try:
            paths = store.tracks(pl_id)
        except Exception:
            return []
        # Filter to paths that actually exist on disk
        return [p for p in paths if os.path.isfile(p)]

    def _on_click(self, item: QListWidgetItem) -> None:
        self._play_btn.setEnabled(True)
        self._load_btn.setEnabled(True)

    def _on_double_click(self, item: QListWidgetItem) -> None:
        paths = self._selected_paths()
        if paths and self._on_play:
            self._on_play(paths)

    def _on_load_btn(self) -> None:
        paths = self._selected_paths()
        if paths and self._on_load:
            self._on_load(paths)

    def _on_play_btn(self) -> None:
        paths = self._selected_paths()
        if paths and self._on_play:
            self._on_play(paths)

    def _on_sync(self) -> None:
        """Trigger SpotifySync in a background thread."""
        if self._sync_thread and self._sync_thread.is_alive():
            self._status.setText("Sync already running…")
            return

        self._sync_btn.setEnabled(False)
        self._status.setText("Authenticating with Spotify…")

        def _worker() -> None:
            try:
                from phi.meta.spotify_user_client import build_user_client
                from phi.core.spotify_sync        import SpotifySync

                user_client = build_user_client()
                if user_client is None or not user_client.available:
                    # Surface specific auth error if available
                    err = (
                        getattr(user_client, "_auth_error", "")
                        if user_client else ""
                    )
                    if not err:
                        err = (
                            "Spotify auth failed.\n"
                            "Register http://localhost:8888/callback as a Redirect URI\n"
                            "at developer.spotify.com/dashboard → your app → Edit."
                        )
                    self._sched_status(err)
                    return

                store   = getattr(self._ctrl, "playlist_store", None)
                library = getattr(self._ctrl, "library",        None)
                if store is None or library is None:
                    self._sched_status("App not ready")
                    return

                syncer = SpotifySync()

                def _prog(msg: str) -> None:
                    self._sched_status(msg)

                result = syncer.run(
                    library          = library,
                    store            = store,
                    download_missing = True,
                    on_progress      = _prog,
                    user_client      = user_client,
                )

                summary = (
                    f"{result.playlists_scraped} pl  ·  "
                    f"{result.tracks_matched} matched  ·  "
                    f"{result.tracks_downloaded} downloaded"
                )
                self._sched_status(summary)
                # Refresh the list on the main thread
                sched = getattr(self._ctrl, "_sched", None)
                if sched:
                    sched(0, self.refresh)
                else:
                    self.refresh()

            except Exception as exc:
                self._sched_status(f"Sync error: {exc}")
            finally:
                sched = getattr(self._ctrl, "_sched", None)
                if sched:
                    sched(0, lambda: self._sync_btn.setEnabled(True))
                else:
                    self._sync_btn.setEnabled(True)

        self._sync_thread = threading.Thread(target=_worker, daemon=True)
        self._sync_thread.start()

    def _sched_status(self, msg: str) -> None:
        """Set status text safely from a background thread."""
        sched = getattr(self._ctrl, "_sched", None)
        if sched:
            sched(0, lambda: self._status.setText(msg))
        else:
            self._status.setText(msg)


class PlaylistRoom(QWidget):
    """
    Playlist studio — three panes: Spotify playlists | library | working playlist.

    Room protocol
    -------------
        on_show()        — light refresh
        on_refresh()     — full rebuild
        sync_transport() — bottom transport bar
    """

    def __init__(self, parent: QWidget | None = None, ctrl: object = None) -> None:
        super().__init__(parent)
        self._ctrl         = ctrl
        self._cache_warm   = False
        self._all_paths:   list[str] = []
        self._filtered:    list[str] = []
        self._playlist:    list[str] = []
        self._build()

    # ── layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Title bar
        bar = QWidget()
        bar.setStyleSheet(f"background: {CARD2};")
        bar_row = QHBoxLayout(bar)
        bar_row.setContentsMargins(16, 8, 16, 8)

        title = QLabel("Playlist Studio")
        title.setStyleSheet(f"color: {ACC}; font-size: 13px; font-weight: bold;")

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("untitled playlist")
        self._name_edit.setMaximumWidth(200)
        self._name_edit.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: 1px solid {ACC2}; "
            f"border-radius: 3px; padding: 3px 8px;"
        )

        save_btn = QPushButton("Save M3U")
        save_btn.setStyleSheet(
            f"color: {FG}; background: {CARD}; border: 1px solid {ACC2}; "
            f"border-radius: 3px; padding: 4px 10px; font-size: 10px;"
        )
        save_btn.clicked.connect(self._on_save)

        load_btn = QPushButton("Load M3U")
        load_btn.setStyleSheet(
            f"color: {MUTED}; background: transparent; border: none; font-size: 9px;"
        )
        load_btn.clicked.connect(self._on_load)

        play_btn = QPushButton("▶ Play")
        play_btn.setStyleSheet(
            f"color: {FG}; background: {ACC2}; border: none; "
            f"border-radius: 3px; padding: 4px 12px; font-size: 10px;"
        )
        play_btn.clicked.connect(self._on_play)

        bar_row.addWidget(title)
        bar_row.addWidget(self._name_edit)
        bar_row.addWidget(save_btn)
        bar_row.addWidget(load_btn)
        bar_row.addStretch()
        bar_row.addWidget(play_btn)
        root.addWidget(bar)

        # Three-pane splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {CARD2}; }}")
        root.addWidget(splitter, stretch=1)

        # ── Far left: Spotify / saved playlists sidebar ───────────────────────
        self._sidebar = _SpotifyPlaylistSidebar(ctrl=self._ctrl)
        self._sidebar.setFixedWidth(200)
        self._sidebar.set_callbacks(
            on_load=self._load_playlist_paths,
            on_play=self._play_playlist_paths,
        )
        splitter.addWidget(self._sidebar)

        # ── Middle: library source ────────────────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 4, 4)
        left_layout.setSpacing(4)

        lbl_l = QLabel("Library")
        lbl_l.setStyleSheet(f"color: {MUTED}; font-size: 9px; font-weight: bold;")

        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("filter…")
        self._filter_edit.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: 1px solid {CARD2}; "
            f"border-radius: 3px; padding: 3px 6px; font-size: 9px;"
        )
        self._filter_edit.textChanged.connect(self._apply_filter)

        self._src_list = QListWidget()
        self._src_list.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: none; font-size: 9px;"
            f"QListWidget::item:selected {{ background: {ACC2}; }}"
        )
        self._src_list.itemDoubleClicked.connect(self._on_src_double)

        left_layout.addWidget(lbl_l)
        left_layout.addWidget(self._filter_edit)
        left_layout.addWidget(self._src_list, stretch=1)
        splitter.addWidget(left)

        # ── Right: working playlist ───────────────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 8, 8, 4)
        right_layout.setSpacing(4)

        lbl_r = QLabel("Working Playlist")
        lbl_r.setStyleSheet(f"color: {MUTED}; font-size: 9px; font-weight: bold;")

        self._pl_list = QListWidget()
        self._pl_list.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: none; font-size: 9px;"
            f"QListWidget::item:selected {{ background: {ACC2}; }}"
        )
        self._pl_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._pl_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        btn_row = QHBoxLayout()
        rm_btn  = QPushButton("Remove")
        rm_btn.setStyleSheet(
            f"color: {MUTED}; background: transparent; border: none; font-size: 9px;"
        )
        rm_btn.clicked.connect(self._on_remove)
        clr_btn = QPushButton("Clear")
        clr_btn.setStyleSheet(
            f"color: {MUTED}; background: transparent; border: none; font-size: 9px;"
        )
        clr_btn.clicked.connect(self._on_clear)
        self._count_lbl = QLabel("0 tracks")
        self._count_lbl.setStyleSheet(f"color: {MUTED}; font-size: 8px;")
        btn_row.addWidget(rm_btn)
        btn_row.addWidget(clr_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._count_lbl)

        right_layout.addWidget(lbl_r)
        right_layout.addWidget(self._pl_list, stretch=1)
        right_layout.addLayout(btn_row)
        splitter.addWidget(right)

        splitter.setSizes([200, 360, 360])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)

        self._mini = MiniTransportWidget(ctrl=self._ctrl)
        root.addWidget(self._mini)

    # ── room protocol ─────────────────────────────────────────────────────────

    def on_show(self) -> None:
        self._sidebar.refresh()
        if not self._cache_warm:
            QTimer.singleShot(0, self.on_refresh)
        else:
            self._reload_library()

    def on_refresh(self) -> None:
        self._sidebar.refresh()
        self._reload_library()
        self._cache_warm = True

    # ── sidebar callbacks ─────────────────────────────────────────────────────

    def _load_playlist_paths(self, paths: list[str]) -> None:
        """Load playlist paths into the working playlist pane (does not play)."""
        lib = self._ctrl.library  # type: ignore[union-attr]
        self._on_clear()
        for p in paths:
            self._playlist.append(p)
            self._pl_list.addItem(lib.display_name(p))
        self._count_lbl.setText(f"{len(self._playlist)} tracks")

    def _play_playlist_paths(self, paths: list[str]) -> None:
        """Load paths into working playlist pane AND play immediately."""
        self._load_playlist_paths(paths)
        if hasattr(self._ctrl, "on_play_album"):
            self._ctrl.on_play_album(paths)  # type: ignore[union-attr]
        elif paths and hasattr(self._ctrl, "on_play_path"):
            self._ctrl.on_play_path(paths[0])  # type: ignore[union-attr]

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

    # ── library reload ────────────────────────────────────────────────────────

    def _reload_library(self) -> None:
        lib = self._ctrl.library  # type: ignore[union-attr]
        self._all_paths = list(lib.playlist)
        self._apply_filter()

    def _apply_filter(self) -> None:
        text = self._filter_edit.text().lower()
        lib  = self._ctrl.library  # type: ignore[union-attr]
        if text:
            self._filtered = [
                p for p in self._all_paths
                if text in (lib.display_name(p) or "").lower()
            ]
        else:
            self._filtered = list(self._all_paths)

        self._src_list.clear()
        for path in self._filtered:
            self._src_list.addItem(lib.display_name(path))

    # ── source list ───────────────────────────────────────────────────────────

    def _on_src_double(self, item: QListWidgetItem) -> None:
        row = self._src_list.row(item)
        if 0 <= row < len(self._filtered):
            path = self._filtered[row]
            self._playlist.append(path)
            lib  = self._ctrl.library  # type: ignore[union-attr]
            self._pl_list.addItem(lib.display_name(path))
            self._count_lbl.setText(f"{len(self._playlist)} tracks")

    # ── playlist controls ─────────────────────────────────────────────────────

    def _on_remove(self) -> None:
        rows = sorted(
            [self._pl_list.row(i) for i in self._pl_list.selectedItems()],
            reverse=True,
        )
        for r in rows:
            self._pl_list.takeItem(r)
            self._playlist.pop(r)
        self._count_lbl.setText(f"{len(self._playlist)} tracks")

    def _on_clear(self) -> None:
        self._pl_list.clear()
        self._playlist = []
        self._count_lbl.setText("0 tracks")

    def _on_play(self) -> None:
        if self._playlist:
            self._ctrl.on_play_album(self._playlist)  # type: ignore[union-attr]

    def _on_save(self) -> None:
        name = self._name_edit.text().strip() or "playlist"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Playlist", f"{name}.m3u", "M3U files (*.m3u *.m3u8)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for p in self._playlist:
                    f.write(p + "\n")
        except OSError:
            pass

    def _on_load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Playlist", os.path.expanduser("~"),
            "M3U files (*.m3u *.m3u8);;All files (*)"
        )
        if not path:
            return
        lib    = self._ctrl.library  # type: ignore[union-attr]
        loaded = []
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and os.path.exists(line):
                        loaded.append(line)
        except OSError:
            return
        self._on_clear()
        for p in loaded:
            self._playlist.append(p)
            self._pl_list.addItem(lib.display_name(p))
        self._count_lbl.setText(f"{len(self._playlist)} tracks")
