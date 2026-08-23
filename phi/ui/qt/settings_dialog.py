# -*- coding: utf-8 -*-
"""phi.ui.qt.settings_dialog — PySide6 preferences dialog.

Replaces phi.ui.settings_dialog.SettingsDialog (tk.Toplevel).

Sections
--------
  General  — watched folder, auto-scan, notifications
  Audio    — crossfade slider, ReplayGain, gapless
  Last.fm  — API credentials + OAuth flow
  CAIRRN   — live forest floor read-out
  About    — version, links

Public surface
--------------
    SettingsDialog(parent, ctrl)  — QDialog, call .exec() to open modal
    load_settings() → dict        — re-exported from phi.ui.settings_dialog
    save_settings(data)           — re-exported from phi.ui.settings_dialog
"""
from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from phi.config import ACC, ACC2, BG, CARD, CARD2, FG, MUTED

# Re-export the framework-agnostic I/O helpers unchanged.
from phi.ui.settings_dialog import load_settings, save_settings  # noqa: F401

_SECTIONS = ("General", "Audio", "Last.fm", "CAIRRN", "About")


class SettingsDialog(QDialog):
    """
    Modal preferences window.

    PhiMainWindow creates it once and stores it as self._settings_dlg;
    subsequent calls just raise() it.
    """

    def __init__(self, parent: QWidget, ctrl: object = None) -> None:
        super().__init__(parent)
        self._ctrl      = ctrl or parent
        self._settings  = load_settings()
        self._pending_token: str = ""

        self.setWindowTitle("phi — Settings")
        self.setModal(True)
        self.setMinimumSize(520, 540)
        self.setStyleSheet(f"QDialog {{ background: {BG}; }}")

        self._build()

    # ── top-level layout ─────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Section strip
        strip = QWidget()
        strip.setStyleSheet(f"background: {CARD2};")
        strip_row = QHBoxLayout(strip)
        strip_row.setContentsMargins(0, 0, 0, 0)
        strip_row.setSpacing(0)

        self._sec_btns: dict[str, QPushButton] = {}
        for name in _SECTIONS:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setStyleSheet(self._sec_style(False))
            btn.clicked.connect(lambda checked, n=name: self._show_section(n))
            self._sec_btns[name] = btn
            strip_row.addWidget(btn)
        strip_row.addStretch()
        root.addWidget(strip)

        # Stacked content
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background: {BG};")
        self._pages: dict[str, QWidget] = {}
        for name, builder in [
            ("General", self._build_general),
            ("Audio",   self._build_audio),
            ("Last.fm", self._build_lastfm),
            ("CAIRRN",  self._build_cairrn),
            ("About",   self._build_about),
        ]:
            page = builder()
            self._pages[name] = page
            self._stack.addWidget(page)
        root.addWidget(self._stack, stretch=1)

        # Footer
        footer = QWidget()
        footer.setStyleSheet(f"background: {BG};")
        footer_row = QHBoxLayout(footer)
        footer_row.setContentsMargins(24, 8, 24, 16)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {CARD2};")

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            f"color: {FG}; background: {CARD2}; border: none; "
            f"border-radius: 3px; padding: 6px 16px; font-size: 11px;"
        )
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(
            f"color: #ffffff; background: {ACC}; border: none; "
            f"border-radius: 3px; padding: 6px 24px; "
            f"font-size: 11px; font-weight: bold;"
        )
        save_btn.clicked.connect(self._save_and_close)

        footer_row.addStretch()
        footer_row.addWidget(cancel_btn)
        footer_row.addWidget(save_btn)

        root.addWidget(sep)
        root.addWidget(footer)

        self._show_section("General")

    # ── section builders ─────────────────────────────────────────────────────

    def _build_general(self) -> QWidget:
        page, layout = self._scrollable_page()

        self._h(layout, "Music Library")

        # Watched folder
        fold_row = QHBoxLayout()
        fold_lbl = QLabel("Watched folder:")
        fold_lbl.setFixedWidth(130)
        fold_lbl.setStyleSheet(f"color: {FG}; font-size: 10px;")
        self._folder_edit = QLineEdit(self._settings.get("watch_folder", ""))
        self._folder_edit.setStyleSheet(self._entry_style())
        browse_btn = QPushButton("Browse…")
        browse_btn.setStyleSheet(
            f"color: {FG}; background: {CARD2}; border: none; "
            f"border-radius: 3px; padding: 4px 10px; font-size: 10px;"
        )
        browse_btn.clicked.connect(self._browse_folder)
        fold_row.addWidget(fold_lbl)
        fold_row.addWidget(self._folder_edit, stretch=1)
        fold_row.addWidget(browse_btn)
        layout.addLayout(fold_row)

        self._auto_scan_cb = QCheckBox("Auto-scan for new files")
        self._auto_scan_cb.setChecked(self._settings.get("auto_scan", True))
        self._cb_style(self._auto_scan_cb)
        layout.addWidget(self._auto_scan_cb)

        self._h(layout, "Display")
        self._notify_cb = QCheckBox("Show macOS notifications when track changes")
        self._notify_cb.setChecked(self._settings.get("notify_on_change", True))
        self._cb_style(self._notify_cb)
        layout.addWidget(self._notify_cb)

        layout.addStretch()
        return page

    def _build_audio(self) -> QWidget:
        page, layout = self._scrollable_page()

        import phi.config as _cfg

        self._h(layout, "Crossfade")

        cf_row = QHBoxLayout()
        cf_lbl = QLabel("Duration (s):")
        cf_lbl.setFixedWidth(100)
        cf_lbl.setStyleSheet(f"color: {FG}; font-size: 10px;")

        self._xfade_slider = QSlider(Qt.Orientation.Horizontal)
        self._xfade_slider.setRange(0, 20)   # 0–10 s in 0.5 s steps
        init_xf = self._settings.get("crossfade_secs", _cfg.CROSSFADE_SECS)
        self._xfade_slider.setValue(int(init_xf * 2))
        self._xfade_slider.setFixedWidth(240)

        self._xfade_val_lbl = QLabel(f"{init_xf:.1f}")
        self._xfade_val_lbl.setFixedWidth(32)
        self._xfade_val_lbl.setStyleSheet(f"color: {ACC}; font-size: 10px;")
        self._xfade_slider.valueChanged.connect(
            lambda v: self._xfade_val_lbl.setText(f"{v / 2:.1f}")
        )

        cf_row.addWidget(cf_lbl)
        cf_row.addWidget(self._xfade_slider)
        cf_row.addWidget(self._xfade_val_lbl)
        cf_row.addStretch()
        layout.addLayout(cf_row)
        self._note(layout, "Set to 0 to disable crossfade and use gapless playback instead.")

        self._h(layout, "ReplayGain")
        self._rg_cb = QCheckBox("Apply ReplayGain volume normalization")
        self._rg_cb.setChecked(self._settings.get("replaygain", True))
        self._cb_style(self._rg_cb)
        layout.addWidget(self._rg_cb)

        self._h(layout, "Gapless Playback")
        self._gapless_cb = QCheckBox("Pre-load next track for zero-gap playback")
        self._gapless_cb.setChecked(self._settings.get("gapless", True))
        self._cb_style(self._gapless_cb)
        layout.addWidget(self._gapless_cb)

        layout.addStretch()
        return page

    def _build_lastfm(self) -> QWidget:
        page, layout = self._scrollable_page()

        self._h(layout, "Last.fm Integration")

        from phi.watch.lastfm import load_creds
        creds     = load_creds()
        connected = bool(creds.get("session_key"))

        self._lfm_status_lbl = QLabel("✓  Connected" if connected else "Not connected")
        self._lfm_status_lbl.setStyleSheet(
            f"color: {ACC if connected else MUTED}; font-size: 10px;"
        )
        layout.addWidget(self._lfm_status_lbl)

        form = QFormLayout()
        form.setSpacing(6)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._api_key_edit    = QLineEdit(creds.get("api_key", ""))
        self._api_secret_edit = QLineEdit(creds.get("api_secret", ""))
        self._api_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        for w in (self._api_key_edit, self._api_secret_edit):
            w.setStyleSheet(self._entry_style())

        lbl_k = QLabel("API Key:")
        lbl_k.setStyleSheet(f"color: {FG}; font-size: 10px;")
        lbl_s = QLabel("API Secret:")
        lbl_s.setStyleSheet(f"color: {FG}; font-size: 10px;")

        form.addRow(lbl_k, self._api_key_edit)
        form.addRow(lbl_s, self._api_secret_edit)
        layout.addLayout(form)

        self._note(
            layout,
            "Get your free API key at last.fm/api/account/create.\n"
            "After entering your key + secret, click Authorize to link your account.",
        )

        auth_btn = QPushButton("Authorize with Last.fm →")
        auth_btn.setStyleSheet(
            f"color: {FG}; background: {ACC2}; border: none; "
            f"border-radius: 3px; padding: 6px 14px; font-size: 10px;"
        )
        auth_btn.clicked.connect(self._authorize_lastfm)
        layout.addWidget(auth_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # Token completion panel (hidden until auth started)
        self._token_panel = QWidget()
        tok_l = QVBoxLayout(self._token_panel)
        tok_l.setContentsMargins(0, 6, 0, 0)
        tok_hint = QLabel(
            "After authorizing in the browser, click Complete Auth:"
        )
        tok_hint.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
        complete_btn = QPushButton("Complete Auth")
        complete_btn.setStyleSheet(
            f"color: {FG}; background: {CARD2}; border: none; "
            f"border-radius: 3px; padding: 4px 12px; font-size: 10px;"
        )
        complete_btn.clicked.connect(self._complete_lastfm)
        tok_l.addWidget(tok_hint)
        tok_l.addWidget(complete_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        self._token_panel.hide()
        layout.addWidget(self._token_panel)

        layout.addStretch()
        return page

    def _build_cairrn(self) -> QWidget:
        page, layout = self._scrollable_page()

        self._h(layout, "Forest Floor")
        self._note(
            layout,
            "Live CAIRRN substrate state. Coherence decays with use; "
            "dropping below 0.50 triggers cache invalidation and recompute.",
        )

        refresh_btn = QPushButton("Refresh ↺")
        refresh_btn.setStyleSheet(
            f"color: {FG}; background: {CARD2}; border: none; "
            f"border-radius: 3px; padding: 3px 10px; font-size: 10px;"
        )
        refresh_btn.clicked.connect(self._refresh_cairrn)
        layout.addWidget(refresh_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self._cairrn_text = QTextEdit()
        self._cairrn_text.setReadOnly(True)
        self._cairrn_text.setStyleSheet(
            f"background: {CARD}; color: {FG}; border: none; "
            f"font-family: Menlo, Courier, monospace; font-size: 9px;"
        )
        self._cairrn_text.setMinimumHeight(280)
        layout.addWidget(self._cairrn_text, stretch=1)

        self._refresh_cairrn()
        return page

    def _refresh_cairrn(self) -> None:
        if not hasattr(self, "_cairrn_text"):
            return
        try:
            floor = getattr(self._ctrl, "floor", None)
            if floor is None:
                content = "floor not available — phi app not running"
            else:
                content = floor.breathe() + "\n\n" + floor.soil_report()
        except Exception as exc:
            content = f"error reading floor state:\n{exc}"
        self._cairrn_text.setPlainText(content)

    def _build_about(self) -> QWidget:
        page, layout = self._scrollable_page()

        phi_lbl = QLabel("φ")
        phi_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        phi_lbl.setStyleSheet(f"color: {ACC}; font-size: 48px; font-weight: bold;")
        layout.addWidget(phi_lbl)
        layout.addSpacing(4)

        name_lbl = QLabel("phi — local music player")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setStyleSheet(f"color: {FG}; font-size: 11px; font-weight: bold;")
        layout.addWidget(name_lbl)

        stack_lbl = QLabel("built with mpv · mutagen · librosa · lrclib")
        stack_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stack_lbl.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        layout.addWidget(stack_lbl)
        layout.addSpacing(16)

        for label, url in [
            ("Last.fm API",   "https://www.last.fm/api"),
            ("LrcLib Lyrics", "https://lrclib.net"),
        ]:
            lnk = QPushButton(label)
            lnk.setStyleSheet(
                f"color: {ACC}; background: transparent; border: none; "
                f"font-size: 10px; text-decoration: underline;"
            )
            lnk.setCursor(Qt.CursorShape.PointingHandCursor)
            lnk.clicked.connect(lambda checked, u=url: webbrowser.open(u))
            layout.addWidget(lnk, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()
        return page

    # ── section navigation ────────────────────────────────────────────────────

    def _show_section(self, name: str) -> None:
        for n, btn in self._sec_btns.items():
            active = n == name
            btn.setChecked(active)
            btn.setStyleSheet(self._sec_style(active))
        self._stack.setCurrentWidget(self._pages[name])
        if name == "CAIRRN":
            self._refresh_cairrn()

    def _sec_style(self, active: bool) -> str:
        bg = ACC2 if active else CARD2
        fg = FG   if active else MUTED
        return (
            f"QPushButton {{ background: {bg}; color: {fg}; border: none; "
            f"padding: 8px 18px; font-size: 10px; }}"
            f"QPushButton:hover {{ background: {ACC2}; color: {FG}; }}"
        )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _scrollable_page(self) -> tuple[QWidget, QVBoxLayout]:
        """Return (page_widget, inner_layout) inside a QScrollArea."""
        outer = QWidget()
        outer_l = QVBoxLayout(outer)
        outer_l.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {BG}; border: none; }}"
            f"QScrollBar:vertical {{ background: {BG}; width: 4px; }}"
            f"QScrollBar::handle:vertical {{ background: {CARD2}; border-radius: 2px; }}"
        )

        inner  = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(4)

        scroll.setWidget(inner)
        outer_l.addWidget(scroll)
        return outer, layout

    def _h(self, layout: QVBoxLayout, text: str) -> None:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {FG}; font-size: 11px; font-weight: bold; padding-top: 10px;"
        )
        layout.addWidget(lbl)

    def _note(self, layout: QVBoxLayout, text: str) -> None:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px;")
        layout.addWidget(lbl)

    def _cb_style(self, cb: QCheckBox) -> None:
        cb.setStyleSheet(
            f"QCheckBox {{ color: {FG}; font-size: 10px; spacing: 6px; }}"
            f"QCheckBox::indicator {{ width: 13px; height: 13px; "
            f"background: {CARD}; border: 1px solid {ACC2}; border-radius: 2px; }}"
            f"QCheckBox::indicator:checked {{ background: {ACC}; border-color: {ACC}; }}"
        )

    def _entry_style(self) -> str:
        return (
            f"background: {CARD}; color: {FG}; border: 1px solid {ACC2}; "
            f"border-radius: 3px; padding: 4px 8px; font-size: 10px;"
        )

    # ── actions ───────────────────────────────────────────────────────────────

    def _browse_folder(self) -> None:
        import os
        folder = QFileDialog.getExistingDirectory(
            self, "Watched folder", os.path.expanduser("~")
        )
        if folder:
            self._folder_edit.setText(folder)

    def _authorize_lastfm(self) -> None:
        key    = self._api_key_edit.text().strip()
        secret = self._api_secret_edit.text().strip()
        if not key or not secret:
            QMessageBox.warning(
                self, "API credentials required",
                "Enter your Last.fm API key and secret first.",
            )
            return
        try:
            from phi.watch.lastfm import get_auth_url
            url, token = get_auth_url(key)
            self._pending_token = token
            webbrowser.open(url)
            self._token_panel.show()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _complete_lastfm(self) -> None:
        key    = self._api_key_edit.text().strip()
        secret = self._api_secret_edit.text().strip()
        token  = self._pending_token
        if not token:
            QMessageBox.warning(self, "Not started", "Click 'Authorize' first.")
            return

        def _exchange() -> None:
            try:
                from phi.watch.lastfm import get_session, save_creds
                sk = get_session(key, secret, token)
                if sk:
                    save_creds(key, secret, sk)
                    QTimer.singleShot(0, self._on_lfm_connected)
                else:
                    QTimer.singleShot(0, lambda: QMessageBox.critical(
                        self, "Auth failed",
                        "Could not get session key. Did you approve in the browser?",
                    ))
            except Exception as exc:
                QTimer.singleShot(
                    0,
                    lambda e=str(exc): QMessageBox.critical(self, "Error", e),
                )

        threading.Thread(target=_exchange, daemon=True).start()

    def _on_lfm_connected(self) -> None:
        self._lfm_status_lbl.setText("✓  Connected")
        self._lfm_status_lbl.setStyleSheet(f"color: {ACC}; font-size: 10px;")
        self._token_panel.hide()
        try:
            from phi.watch.lastfm import build_scrobbler
            self._ctrl._scrobbler = build_scrobbler(  # type: ignore[union-attr]
                self._ctrl._sched  # type: ignore[union-attr]
            )
        except Exception:
            pass

    # ── save ──────────────────────────────────────────────────────────────────

    def _save_and_close(self) -> None:
        import phi.config as _cfg

        data = dict(self._settings)
        data["watch_folder"]     = self._folder_edit.text().strip()
        data["auto_scan"]        = self._auto_scan_cb.isChecked()
        data["notify_on_change"] = self._notify_cb.isChecked()
        data["crossfade_secs"]   = self._xfade_slider.value() / 2.0
        data["replaygain"]       = self._rg_cb.isChecked()
        data["gapless"]          = self._gapless_cb.isChecked()
        save_settings(data)

        # Apply live
        _cfg.CROSSFADE_SECS = data["crossfade_secs"]
        _cfg.GAPLESS        = data["gapless"]

        folder = data.get("watch_folder", "")
        if folder and hasattr(self._ctrl, "watcher"):
            self._ctrl.watcher.watch(folder)  # type: ignore[union-attr]
            self._ctrl.playlist_panel.set_watch(  # type: ignore[union-attr]
                True, folder.split("/")[-1]
            )

        self.accept()
