# -*- coding: utf-8 -*-
"""phi.ui._app._keys — keyboard bindings (Qt)."""
from __future__ import annotations


class _KeysMixin:
    """Install JimKeyWatcher and ⌘-shortcuts via PySide6 QShortcut."""

    def _bind_keys(self) -> None:
        from phi.ui.qt.keys import JimKeyWatcher

        self.jim = JimKeyWatcher(
            self,
            on_prev       = self.on_prev,
            on_next       = self.on_next,
            on_seek_fwd   = lambda: self._seek_rel(+5),
            on_seek_back  = lambda: self._seek_rel(-5),
            on_play_pause = self.on_play_pause,
            on_deselect   = lambda: (
                self.playlist_panel.clear_search(), self.focus()
            ),
            on_vol_up     = lambda: self._vol_step(+0.05),
            on_vol_down   = lambda: self._vol_step(-0.05),
            on_rooms      = self.toggle_rooms,
            on_mute       = self.on_toggle_mute,
            on_shuffle    = self.on_toggle_shuffle,
            on_repeat     = self.on_cycle_repeat,
            on_sidebar    = self.sidebar.toggle,
            on_sleep      = self.open_sleep_timer,
            on_escape     = lambda: (
                self.playlist_panel.clear_search(), self.focus()
            ),
            on_help       = self._jim_help.toggle,
            on_overlay    = self._overlay.show,
            on_fullscreen = self.toggle_fullscreen,
            cairrn        = getattr(self, "cairrn_dispatcher", None),
        )
        # ⌘] / ⌘↑ → navigate deeper   ⌘↓ → navigate shallower
        self.jim.add_modifier("<Command-bracketright>", self.navigate_deeper)
        self.jim.add_modifier("<Control-bracketright>", self.navigate_deeper)
        self.jim.add_modifier("<Command-Up>",           self.navigate_deeper)
        self.jim.add_modifier("<Control-Up>",           self.navigate_deeper)
        self.jim.add_modifier("<Command-Down>",         self.navigate_shallower)
        self.jim.add_modifier("<Control-Down>",         self.navigate_shallower)
        # ⌘, / ⌘⇧, → Preferences (menu bar handles ⌘,; ⌘⇧, kept as fallback)
        self.jim.add_modifier("<Command-Shift-comma>", self.open_settings)
        self.jim.add_modifier("<Control-Shift-comma>", self.open_settings)
        # ⌘⇧M → mini player  (⌘M freed for standard macOS Minimize)
        self.jim.add_modifier("<Command-Shift-m>",  self.toggle_mini_player)
        self.jim.add_modifier("<Control-Shift-m>",  self.toggle_mini_player)

        _pages = self._page_names
        for _i, _pg in enumerate(_pages, start=1):
            self.jim.add_modifier(f"<Command-Key-{_i}>",  lambda p=_pg: self.go_to_page(p))
            self.jim.add_modifier(f"<Control-Key-{_i}>",  lambda p=_pg: self.go_to_page(p))
        self.jim.add_modifier("<Command-b>",      lambda: self.toggle_page("library"))
        self.jim.add_modifier("<Control-b>",      lambda: self.toggle_page("library"))
        self.jim.add_modifier("<Command-slash>",  lambda: self._library_page.toggle_deep())
        self.jim.add_modifier("<Control-slash>",  lambda: self._library_page.toggle_deep())
        self.jim.add_modifier("<Command-period>", self.toggle_ml_table)
        self.jim.add_modifier("<Control-period>", self.toggle_ml_table)
        # ⌘⇧Z → z-spine toggle  (⌘Z freed for standard macOS Undo)
        self.jim.add_modifier("<Command-Shift-z>",  self.toggle_z_spine)
        self.jim.add_modifier("<Control-Shift-z>",  self.toggle_z_spine)

        self.jim.install()
