# -*- coding: utf-8 -*-
"""phi.ui.qt._app_overlays — dialog / overlay launcher mixin for PhiMainWindow."""
from __future__ import annotations


class _OverlaysMixin:
    """Opens settings, mini player, sleep timer, onboarding and tag editor."""

    def open_settings(self) -> None:
        """Open (or bring to front) the Settings dialog."""
        from phi.ui.qt.settings_dialog import SettingsDialog
        dlg = getattr(self, "_settings_dlg", None)
        if dlg is not None and dlg.isVisible():
            dlg.raise_()
            dlg.activateWindow()
        else:
            self._settings_dlg = SettingsDialog(self, ctrl=self)
            self._settings_dlg.exec()

    def toggle_mini_player(self) -> None:
        """Show or hide the compact always-on-top mini player."""
        from phi.ui.qt.mini_player import MiniPlayer
        if not hasattr(self, "_mini") or self._mini is None:
            self._mini = MiniPlayer(self)
        else:
            self._mini.toggle()

    def open_sleep_timer(self) -> None:
        """Open the sleep timer dialog."""
        from phi.ui.qt.sleep_timer import SleepTimerDialog
        SleepTimerDialog(self, ctrl=self).exec()

    def _show_onboarding(self) -> None:
        """Show first-launch welcome dialog if library is empty."""
        from phi.ui.qt.onboarding import show_if_empty
        show_if_empty(self)

    def on_tag_edit(self, paths: list[str]) -> None:
        """Open the batch tag editor for the given paths."""
        from phi.ui.qt.tag_editor import TagEditorDialog
        TagEditorDialog(self, ctrl=self, paths=paths).exec()
