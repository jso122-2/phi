# -*- coding: utf-8 -*-
"""phi.ui.settings_dialog — settings persistence helpers.

The full SettingsDialog UI lives in phi.ui.qt.settings_dialog (PySide6).
This module is kept solely for the framework-agnostic load/save functions
that are imported by several mixin files and phi.ui.qt.settings_dialog.
"""
from __future__ import annotations

import json
from pathlib import Path

_SETTINGS_FILE = Path.home() / ".phi" / "settings.json"

_settings_cache: dict | None = None


def load_settings() -> dict:
    global _settings_cache
    if _settings_cache is not None:
        return _settings_cache
    try:
        _settings_cache = json.loads(_SETTINGS_FILE.read_text())
    except Exception:
        _settings_cache = {}
    return _settings_cache


def save_settings(data: dict) -> None:
    global _settings_cache
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_FILE.write_text(json.dumps(data, indent=2))
    _settings_cache = dict(data)
