# -*- coding: utf-8 -*-
"""phi.ui.qt.onboarding — PySide6 first-launch welcome dialog.

Replaces phi.ui.onboarding.OnboardingDialog (tk.Toplevel).

Usage
-----
    from phi.ui.qt.onboarding import OnboardingDialog, show_if_empty
    show_if_empty(ctrl)
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from phi.config import ACC, ACC2, BG, FG, MUTED


def show_if_empty(ctrl: object) -> None:
    """Show the onboarding dialog if the library is empty."""
    if ctrl.library.size > 0:  # type: ignore[union-attr]
        return
    parent = ctrl if isinstance(ctrl, QWidget) else None
    dlg = OnboardingDialog(parent, ctrl)
    dlg.exec()


class OnboardingDialog(QDialog):
    """
    Modal welcome screen.

    Guides the user to browse for a music folder or dismiss.
    """

    def __init__(self, parent: QWidget | None, ctrl: object = None) -> None:
        super().__init__(parent)
        self._ctrl = ctrl or parent
        self.setWindowTitle("")
        self.setModal(True)
        self.setFixedSize(500, 360)
        self.setStyleSheet(f"QDialog {{ background: {BG}; }}")
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 20)
        root.setSpacing(0)
        root.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        phi_lbl = QLabel("φ")
        phi_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        phi_lbl.setStyleSheet(f"color: {ACC}; font-size: 64px; font-weight: bold;")
        root.addWidget(phi_lbl)

        name_lbl = QLabel("phi")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setStyleSheet(f"color: {FG}; font-size: 22px; font-weight: bold;")
        root.addWidget(name_lbl)

        sub_lbl = QLabel("your local music player")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_lbl.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        root.addWidget(sub_lbl)
        root.addSpacing(20)

        div = QWidget()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {ACC2};")
        root.addWidget(div)
        root.addSpacing(16)

        add_lbl = QLabel("Add your music library to get started.")
        add_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        add_lbl.setStyleSheet(f"color: {FG}; font-size: 11px;")
        root.addWidget(add_lbl)
        root.addSpacing(4)

        hint_lbl = QLabel(
            "Drag folders onto the Tracks list  ·  or click Browse below"
        )
        hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_lbl.setWordWrap(True)
        hint_lbl.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        root.addWidget(hint_lbl)
        root.addSpacing(24)

        browse_btn = QPushButton("Browse for music folder")
        browse_btn.setStyleSheet(
            f"color: #ffffff; background: {ACC}; border: none; "
            f"border-radius: 4px; padding: 10px 20px; "
            f"font-size: 12px; font-weight: bold;"
        )
        browse_btn.clicked.connect(self._browse)
        root.addWidget(browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addSpacing(12)

        skip_btn = QPushButton("Skip — I'll add music later")
        skip_btn.setStyleSheet(
            f"color: {MUTED}; background: transparent; border: none; font-size: 9px;"
        )
        skip_btn.clicked.connect(self.reject)
        root.addWidget(skip_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _browse(self) -> None:
        import os
        folder = QFileDialog.getExistingDirectory(
            self,
            "Choose your music folder",
            os.path.expanduser("~"),
        )
        if folder:
            self.accept()
            if hasattr(self._ctrl, "on_add_folder_path"):
                self._ctrl.on_add_folder_path(folder)  # type: ignore[union-attr]
