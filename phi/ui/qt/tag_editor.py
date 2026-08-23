# -*- coding: utf-8 -*-
"""phi.ui.qt.tag_editor — PySide6 batch tag editor dialog.

Replaces phi.ui.tag_editor.TagEditorDialog (tk.Toplevel).

Usage
-----
    TagEditorDialog(parent, paths=["/path/a.mp3", ...]).exec()

The _read_tags / _write_tags functions are reused unchanged from
phi.ui.tag_editor (they are framework-agnostic).
"""
from __future__ import annotations

import os
import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from phi.config import ACC, ACC2, BG, CARD, CARD2, FG, MUTED
from phi.ui.tag_editor import _FIELDS, _VARIOUS, _read_tags, _write_tags


class TagEditorDialog(QDialog):
    """
    Modal batch tag editor.

    Parameters
    ----------
    parent  QWidget (PhiMainWindow)
    ctrl    controller (for _flash and meta_cache access)
    paths   list of audio file paths to edit
    """

    def __init__(
        self,
        parent: QWidget,
        ctrl: object = None,
        paths: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self._ctrl  = ctrl or parent
        self._paths = paths or []
        self._vars:  dict[str, QLineEdit] = {}
        self._orig:  dict[str, str]       = {}

        n = len(self._paths)
        self.setWindowTitle(f"Edit Tags — {n} track{'s' if n != 1 else ''}")
        self.setModal(True)
        self.setMinimumSize(480, 440)
        self.setStyleSheet(f"QDialog {{ background: {BG}; }}")

        self._build()
        self._load_async()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 20, 32, 16)
        root.setSpacing(8)

        # Header
        hdr_title = QLabel("Edit Tags")
        hdr_title.setStyleSheet(f"color: {FG}; font-size: 13px; font-weight: bold;")
        n = len(self._paths)
        sub_text  = os.path.basename(self._paths[0]) if n == 1 else f"{n} tracks selected"
        hdr_sub   = QLabel(sub_text)
        hdr_sub.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
        root.addWidget(hdr_title)
        root.addWidget(hdr_sub)

        # Loading indicator (hidden once fields load)
        self._loading_lbl = QLabel("Reading tags…")
        self._loading_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
        root.addWidget(self._loading_lbl)

        # Fields form (populated async)
        self._form_widget = QWidget()
        self._form_layout = QFormLayout(self._form_widget)
        self._form_layout.setContentsMargins(0, 0, 0, 0)
        self._form_layout.setSpacing(6)
        self._form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(self._form_widget)
        self._form_widget.hide()

        root.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            f"color: {FG}; background: {CARD2}; border: none; "
            f"border-radius: 3px; padding: 6px 20px; font-size: 11px;"
        )
        cancel_btn.clicked.connect(self.reject)

        self._save_btn = QPushButton("Save")
        self._save_btn.setStyleSheet(
            f"color: #ffffff; background: {ACC}; border: none; "
            f"border-radius: 3px; padding: 6px 24px; "
            f"font-size: 11px; font-weight: bold;"
        )
        self._save_btn.clicked.connect(self._save)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._save_btn)
        root.addLayout(btn_row)

    def _load_async(self) -> None:
        def _worker() -> None:
            values = _read_tags(self._paths)
            self._orig = values
            # schedule back to Qt main thread
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._populate(values))

        threading.Thread(target=_worker, daemon=True).start()

    def _populate(self, values: dict[str, str]) -> None:
        self._loading_lbl.hide()
        for label, key in _FIELDS:
            edit = QLineEdit()
            edit.setText(values.get(key, ""))
            edit.setStyleSheet(
                f"background: {CARD}; color: {FG}; border: 1px solid {ACC2}; "
                f"border-radius: 3px; padding: 4px 8px; font-size: 10px;"
            )
            lbl_w = QLabel(label)
            lbl_w.setStyleSheet(f"color: {MUTED}; font-size: 9px;")

            # Clear <various> on focus
            def _on_focus(_, e=edit):
                if e.text() == _VARIOUS:
                    e.clear()

            edit.focusInEvent = _on_focus  # type: ignore[method-assign]
            self._vars[key] = edit
            self._form_layout.addRow(lbl_w, edit)

        self._form_widget.show()
        self.adjustSize()

    def _save(self) -> None:
        values = {
            key: self._vars[key].text()
            for _, key in _FIELDS
            if key in self._vars
        }
        self._save_btn.setEnabled(False)
        self._save_btn.setText("Saving…")
        threading.Thread(
            target=self._write_worker, args=(values,), daemon=True
        ).start()

    def _write_worker(self, values: dict[str, str]) -> None:
        failed = _write_tags(self._paths, values)
        try:
            cache = getattr(self._ctrl, "meta_cache", None)
            if cache:
                for p in self._paths:
                    cache.invalidate(p)
        except Exception:
            pass
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._finish(failed))

    def _finish(self, failed: list[str]) -> None:
        n_ok = len(self._paths) - len(failed)
        if failed:
            QMessageBox.warning(
                self,
                "Partial write",
                f"Wrote {n_ok} tracks. Failed on:\n"
                + "\n".join(os.path.basename(f) for f in failed[:5]),
            )
            self._save_btn.setEnabled(True)
            self._save_btn.setText("Save")
        else:
            if hasattr(self._ctrl, "_flash"):
                self._ctrl._flash(f"Tags saved ({n_ok} track{'s' if n_ok != 1 else ''})")  # type: ignore[union-attr]
            self.accept()
