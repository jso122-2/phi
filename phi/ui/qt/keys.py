# -*- coding: utf-8 -*-
"""phi.ui.qt.keys — Jim keyboard bindings for PySide6.

Replaces phi.watch.jim_keys.JimKeyWatcher (Tkinter bind_all).

Strategy
--------
Modifier chords (⌘K, ⌘B, F11, etc.) → QShortcut with ApplicationShortcut
context, attached to PhiMainWindow.

Single-char Jim keys (i/w/a/l/d/j/h/f/e/g/b/t/s/r/m/space/arrows) → handled
in PhiMainWindow.keyPressEvent with an entry-focus guard, same semantic as
the Tk version's bind_all() + Entry check.

JIM_BINDING_TABLE is preserved here for the help overlay.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QLineEdit, QWidget

from phi.engine.cairrn._constants import ACTION_CAIRRN

if TYPE_CHECKING:
    from phi.engine.cairrn.router import PhiCairrnRouter


# ── Canonical binding table (copied from old jim_keys.py) ─────────────────────

JIM_BINDING_TABLE: list[tuple[str, str, str]] = [
    ("Navigation",  "i",      "previous track  (cursor up)"),
    ("Navigation",  "w",      "next track  (cursor down)"),
    ("Navigation",  "a",      "seek +5 s  (forward)"),
    ("Navigation",  "l",      "seek −5 s  (back)"),
    ("Navigation",  "d",      "play / pause  (select)"),
    ("Navigation",  "j",      "clear search  (deselect)"),
    ("Navigation",  "h",      "volume up  (zoom in)"),
    ("Navigation",  "f",      "volume down  (zoom out)"),
    ("Navigation",  "e",      "toggle rooms (enter / return to playing)"),
    ("Navigation",  "k + s",  "toggle rooms (tab chord)"),
    ("Playback",    "Space",  "play / pause"),
    ("Playback",    "m",      "mute toggle"),
    ("Playback",    "s",      "toggle shuffle"),
    ("Playback",    "r",      "cycle repeat"),
    ("Playback",    "←  →",   "seek −5 s / +5 s"),
    ("Playback",    "↑  ↓",   "volume up / down"),
    ("UI",          "b",      "sidebar toggle"),
    ("UI",          "⌘B",     "library toggle (full track list)"),
    ("UI",          "⌘/",     "library deep browser toggle (spine + genre tree)"),
    ("UI",          "⌘1–⌘6",  "jump to page: playing · queue · library · playlist · genre · mixer"),
    ("UI",          "⌘,",     "preferences  (macOS standard → opens settings)"),
    ("UI",          "⌘]  ⌘↑", "navigate deeper  (playing → library → playlist → genre → mixer → ML)"),
    ("UI",          "⌘↓",    "navigate shallower  (reverse of ⌘↑)"),
    ("UI",          "t",      "sleep timer"),
    ("UI",          "⌘K",     "command palette"),
    ("UI",          "⌘⇧M",    "mini player toggle"),
    ("UI",          "⌘M",     "minimize window  (macOS standard)"),
    ("UI",          "⌘H",     "hide phi  (macOS standard)"),
    ("UI",          "⌘W",     "close window  (macOS standard)"),
    ("UI",          "⌘Q",     "quit phi  (macOS standard)"),
    ("UI",          "⌘⌃F",    "full screen  (macOS standard)"),
    ("UI",          "⌘⇧Z",    "z-spine toggle"),
    ("UI",          "F11",    "fullscreen  (non-macOS)"),
    ("UI",          "Esc",    "clear search / dismiss"),
    ("UI",          "g",      "show jim bindings"),
]


def _in_entry() -> bool:
    """True when a text-input widget currently holds keyboard focus."""
    w = QApplication.focusWidget()
    return isinstance(w, QLineEdit)


class JimKeyWatcher:
    """
    Installs Jim key bindings on a QMainWindow.

    Constructor mirrors the old Tkinter JimKeyWatcher exactly so _KeysMixin
    requires no changes.

    Usage::

        watcher = JimKeyWatcher(window, on_next=app.on_next, ...)
        watcher.install()
    """

    def __init__(
        self,
        root: QWidget,
        *,
        on_prev:       Callable,
        on_next:       Callable,
        on_seek_fwd:   Callable,
        on_seek_back:  Callable,
        on_play_pause: Callable,
        on_deselect:   Callable,
        on_vol_up:     Callable,
        on_vol_down:   Callable,
        on_rooms:      Callable,
        on_mute:       Callable,
        on_shuffle:    Callable,
        on_repeat:     Callable,
        on_sidebar:    Callable,
        on_sleep:      Callable,
        on_escape:     Callable,
        on_help:       Callable,
        on_overlay:    Callable | None = None,
        on_fullscreen: Callable | None = None,
        cairrn:        Optional["PhiCairrnRouter"] = None,
    ) -> None:
        self._root   = root
        self._cairrn = cairrn
        self._cbs: dict[str, Callable] = {
            "prev":       on_prev,
            "next":       on_next,
            "seek_fwd":   on_seek_fwd,
            "seek_back":  on_seek_back,
            "play_pause": on_play_pause,
            "deselect":   on_deselect,
            "vol_up":     on_vol_up,
            "vol_down":   on_vol_down,
            "rooms":      on_rooms,
            "mute":       on_mute,
            "shuffle":    on_shuffle,
            "repeat":     on_repeat,
            "sidebar":    on_sidebar,
            "sleep":      on_sleep,
            "escape":     on_escape,
            "help":       on_help,
        }
        if on_overlay is not None:
            self._cbs["overlay"] = on_overlay
        if on_fullscreen is not None:
            self._cbs["fullscreen"] = on_fullscreen

        self._k_held = False
        self._shortcuts: list[QShortcut] = []

    # ── public ────────────────────────────────────────────────────────────────

    def install(self) -> None:
        """Attach all key bindings to the root window."""
        self._setup_shortcuts()

        # Register the key-event handler on the root window so it receives
        # all key events not consumed by child widgets.
        # PhiMainWindow.keyPressEvent calls handle_key() on self.jim.
        # (wired in PhiMainWindow._bind_keys)

    def add(self, key: str, action: str, callback: Callable) -> None:
        """Register an extra action.  (key is the Tk-style string, ignored.)"""
        self._cbs[action] = callback

    def add_modifier(self, key: str, callback: Callable) -> None:
        """Bind a modifier chord.  key is Tk-style e.g. '<Command-comma>'."""
        qs = self._tk_key_to_qs(key)
        if qs:
            sc = QShortcut(QKeySequence(qs), self._root)
            sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
            sc.activated.connect(callback)
            self._shortcuts.append(sc)

    def handle_key(self, event) -> bool:
        """
        Called from PhiMainWindow.keyPressEvent.

        Returns True if the event was consumed (caller should call
        event.accept()), False to let Qt propagate normally.
        """
        if _in_entry():
            return False

        # Suppress OS key-repeat for actions that trigger a full track transition
        # or playback-state change.  Seek/volume keys intentionally keep
        # auto-repeat so holding an arrow key keeps nudging the position.
        if event.isAutoRepeat():
            ch = event.text().lower()
            if ch in ("i", "w", "d") or event.key() == Qt.Key.Key_Space:
                return True  # consume the repeat event; do not act

        key = event.key()
        mods = event.modifiers()
        no_mod = mods == Qt.KeyboardModifier.NoModifier

        if no_mod:
            ch = event.text().lower()
            single_map = {
                "i": "prev",
                "w": "next",
                "a": "seek_fwd",
                "l": "seek_back",
                "d": "play_pause",
                "j": "deselect",
                "h": "vol_up",
                "f": "vol_down",
                "e": "rooms",
                "g": "help",
                "m": "mute",
                "r": "repeat",
                "b": "sidebar",
                "t": "sleep",
            }
            # k+s chord
            if ch == "k":
                self._k_held = True
                return True
            if ch == "s":
                if self._k_held:
                    self._call("rooms")
                else:
                    self._call("shuffle")
                return True
            if ch in single_map:
                self._call(single_map[ch])
                return True

            # space
            if key == Qt.Key.Key_Space:
                self._call("play_pause")
                return True

        # arrow keys (no modifier)
        if no_mod:
            arrow_map = {
                Qt.Key.Key_Left:  "seek_back",
                Qt.Key.Key_Right: "seek_fwd",
                Qt.Key.Key_Up:    "vol_up",
                Qt.Key.Key_Down:  "vol_down",
            }
            if key in arrow_map:
                self._call(arrow_map[key])
                return True

        if key == Qt.Key.Key_Escape:
            self._call("escape")
            return True

        return False

    def handle_key_release(self, event) -> bool:
        if event.key() == Qt.Key.Key_K:
            self._k_held = False
        return False

    # ── internal ───────────────────────────────────────────────────────────────

    def _call(self, action: str) -> None:
        # 1. UI callback fires immediately — CAIRRN never blocks an action.
        cb = self._cbs.get(action)
        if cb:
            try:
                cb()
            except Exception:
                pass

        # 2. Route through CAIRRN as a non-blocking side-effect.
        #    The action→hub mapping lives in ACTION_CAIRRN (_constants.py).
        #    If the router is unavailable the action still completed above.
        if self._cairrn is not None:
            hub, metric = ACTION_CAIRRN.get(action, ("CODE", 0.30))
            try:
                self._cairrn.route_key(action, hub, metric)
            except Exception:
                pass

    def _setup_shortcuts(self) -> None:
        overlay_cb    = self._cbs.get("overlay",    lambda: None)
        fullscreen_cb = self._cbs.get("fullscreen", lambda: None)
        rooms_cb      = self._cbs.get("rooms",      lambda: None)

        chord_map = {
            "Ctrl+K":      overlay_cb,
            "Meta+K":      overlay_cb,    # macOS Cmd
            "Ctrl+L":      overlay_cb,
            "Meta+L":      overlay_cb,
            "F11":         fullscreen_cb,
            "Ctrl+/":      rooms_cb,
            "Meta+/":      rooms_cb,
        }
        for seq, cb in chord_map.items():
            sc = QShortcut(QKeySequence(seq), self._root)
            sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
            sc.activated.connect(cb)
            self._shortcuts.append(sc)

    @staticmethod
    def _tk_key_to_qs(tk_key: str) -> str:
        """Convert Tk key string like '<Command-comma>' to Qt key sequence."""
        tk_key = tk_key.strip("<>")
        tk_key = tk_key.replace("Command-", "Meta+")
        tk_key = tk_key.replace("Control-", "Ctrl+")
        tk_key = tk_key.replace("comma", ",")
        tk_key = tk_key.replace("period", ".")
        tk_key = tk_key.replace("Key-", "")
        return tk_key
