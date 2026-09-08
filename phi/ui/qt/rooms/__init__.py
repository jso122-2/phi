# -*- coding: utf-8 -*-
"""phi.ui.qt.rooms — Qt room pages.

Each room from phi/ui/rooms/ is ported as a QWidget.
Rooms not yet ported remain as StubRoom placeholders.

Exports (all callable as ClassName(parent=..., ctrl=...))
---------------------------------------------------------
    QueueRoom       — live playback queue + CAIRRN dispatch panel (magnum opus)
    LibraryPage     — full library browser with album spines
    PlaylistRoom    — two-pane drag-and-build playlist studio
    MixerRoom       — BPM / key compatibility mixer
    GenreRoom       — full ASCII genre graph with fractal zoom
    MLDragonPage    — dragon curve visualiser + D4 scoring panel
    MLInferencePage — D1–D4 ranked library scores (SongDerivativeModel)
    MLForgePage     — MetaClipper + D4XGBoost training station
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from phi.config import ACC, MUTED


# ── StubRoom ─────────────────────────────────────────────────────────────────

class StubRoom(QWidget):
    """Minimal placeholder that silently accepts all room-protocol calls."""

    def __init__(
        self,
        room_name: str,
        ctrl: object,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._ctrl = ctrl
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel(room_name)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 28px; font-family: Menlo, monospace;"
        )
        sub = QLabel("# TODO: /refactor — port to Qt")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color: {ACC}; font-size: 11px;")
        layout.addWidget(lbl)
        layout.addWidget(sub)

    def refresh(self, *args, **kwargs) -> None:          pass
    def update_transport(self, *args, **kwargs) -> None: pass
    def set_playing(self, *args, **kwargs) -> None:      pass
    def on_show(self) -> None:                           pass
    def on_refresh(self) -> None:                        pass
    def sync_transport(self, *args, **kwargs) -> None:   pass
    def mark_playing(self, *args, **kwargs) -> None:     pass


# ── Ported rooms ──────────────────────────────────────────────────────────────

from phi.ui.qt.rooms.queue_room    import QueueRoom
from phi.ui.qt.rooms.library_room  import LibraryPage
from phi.ui.qt.rooms.playlist_room import PlaylistRoom
from phi.ui.qt.rooms.mixer_room    import MixerRoom
from phi.ui.qt.rooms.genre_room    import GenreRoom


# ── ML rooms ─────────────────────────────────────────────────────────────────

from phi.ui.qt.rooms.dragon_room    import MLDragonPage
from phi.ui.qt.rooms.inference_room import MLInferencePage
from phi.ui.qt.rooms.forge_room     import MLForgePage
from phi.ui.qt.rooms.studio_room    import MLStudioPage


# ── Z-spine rooms ─────────────────────────────────────────────────────────────

try:
    from phi.ui.qt.rooms.discovery_room import DiscoveryRoom as ZSpinePage
except Exception as _disc_exc:  # noqa: BLE001
    import sys as _sys
    print(f"[phi.ui.qt.rooms] discovery_room failed to load: {_disc_exc}", file=_sys.stderr)

    class ZSpinePage(StubRoom):  # type: ignore[no-redef]
        """Fallback stub if DiscoveryRoom fails to import (e.g. PySide6 absent)."""
        def __init__(self, parent: QWidget | None = None, ctrl: object = None) -> None:
            super().__init__("Z  /  DISCOVERY", ctrl, parent)


__all__ = [
    "StubRoom",
    "QueueRoom",
    "LibraryPage",
    "PlaylistRoom",
    "MixerRoom",
    "GenreRoom",
    "MLDragonPage",
    "MLInferencePage",
    "MLForgePage",
    "MLStudioPage",
    "ZSpinePage",
]
