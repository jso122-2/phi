# -*- coding: utf-8 -*-
"""phi.ui.qt._app_menu — macOS native menu bar mixin for PhiMainWindow."""
from __future__ import annotations

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QMenuBar


class _MenuMixin:
    """Provides _build_macos_menu() for PhiMainWindow."""

    def _build_macos_menu(self) -> None:
        """Build a native macOS menu bar with standard roles and shortcuts.

        Qt only creates the macOS Application menu (and therefore handles
        Cmd+Q, Cmd+H, etc.) when a QMenuBar with at least one menu exists.
        Standard MenuRole values let Qt map actions into the auto-generated
        AppKit Application menu, so Dock > Quit, Cmd+Q, and Preferences all
        behave correctly.

        Do NOT add a "Hide" action here — AppKit auto-inserts "Hide [App]"
        (Cmd+H) and "Hide Others" (Cmd+Opt+H) into the Application menu on
        its own; adding a duplicate would create two conflicting items.

        Qt key-sequence note: on macOS, Qt maps Ctrl → Cmd (⌘) and
        Meta → Control (⌃), so QKeySequence("Ctrl+Q") = ⌘Q.
        """
        mb = QMenuBar(self)
        mb.setNativeMenuBar(True)

        # Application menu
        phi_menu = mb.addMenu("phi")

        prefs_action = QAction("Preferences…", self)
        prefs_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        prefs_action.setShortcut(QKeySequence("Ctrl+,"))
        prefs_action.triggered.connect(self.open_settings)
        phi_menu.addAction(prefs_action)

        quit_action = QAction("Quit phi", self)
        quit_action.setMenuRole(QAction.MenuRole.QuitRole)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(QApplication.quit)
        phi_menu.addAction(quit_action)

        # Window menu
        win_menu = mb.addMenu("Window")

        minimize_action = QAction("Minimize", self)
        minimize_action.setShortcut(QKeySequence("Ctrl+M"))
        minimize_action.triggered.connect(self.showMinimized)
        win_menu.addAction(minimize_action)

        close_action = QAction("Close", self)
        close_action.setShortcut(QKeySequence("Ctrl+W"))
        close_action.triggered.connect(self.close)
        win_menu.addAction(close_action)

        win_menu.addSeparator()

        fullscreen_action = QAction("Enter Full Screen", self)
        fullscreen_action.setShortcut(QKeySequence("Ctrl+Meta+F"))
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        win_menu.addAction(fullscreen_action)

        win_menu.addSeparator()

        mini_action = QAction("Mini Player", self)
        mini_action.setShortcut(QKeySequence("Ctrl+Shift+M"))
        mini_action.triggered.connect(self.toggle_mini_player)
        win_menu.addAction(mini_action)

        self.setMenuBar(mb)
