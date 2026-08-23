# -*- coding: utf-8 -*-
"""phi.ui.qt.rooms.genre_room — Qt full-page genre graph room.

Replaces phi.ui.rooms.genre_room.GenreRoom (tk.Frame).

Layout
------
┌──────────────────────────────────────────────────────┐
│  genre graph / fractal zoom  (GenreGraphView)        │
│  ASCII network — zoom into genres → subgenres → tracks│
├──────────────────────────────────────────────────────┤
│  mini transport                                       │
└──────────────────────────────────────────────────────┘

Room protocol: on_show(), on_refresh(), sync_transport(), mark_playing()
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QVBoxLayout, QWidget

from phi.ui.qt.genre_graph import GenreGraphView
from phi.ui.qt.rooms._mini_transport import MiniTransportWidget


class GenreRoom(QWidget):
    """Room page: full-page ASCII genre network with fractal zoom."""

    def __init__(
        self,
        parent: QWidget | None = None,
        ctrl:   object         = None,
    ) -> None:
        super().__init__(parent)
        self._ctrl    = ctrl
        self._built   = False
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._graph = GenreGraphView(ctrl=self._ctrl, parent=self)
        root.addWidget(self._graph, stretch=1)

        self._mini = MiniTransportWidget(ctrl=self._ctrl, parent=self)
        root.addWidget(self._mini)

        self._built = True

    # ── room protocol ─────────────────────────────────────────────────────────

    def on_show(self) -> None:
        """Called when this room becomes visible."""
        if not self._graph._tree:
            self._graph.rebuild()
        else:
            self._graph.redraw()

    def on_refresh(self) -> None:
        """Called when the library has changed."""
        self._graph.rebuild()

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
        self._graph.mark_playing(path)

    def set_playing(self, path: Optional[str] = None, **kwargs) -> None:
        self.mark_playing(path)
