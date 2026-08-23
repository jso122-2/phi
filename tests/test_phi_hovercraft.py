# -*- coding: utf-8 -*-
"""Launch warmup must not rebuild stacked rooms on the main thread."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from phi.ui._app._warmup import _WarmupMixin


class _Dummy(_WarmupMixin):
    def __init__(self) -> None:
        self.floor = MagicMock()
        self._library_page = MagicMock()
        self._genre_page = MagicMock()
        self._playlist_page = MagicMock()


def test_warmup_pulses_playing_only():
    app = _Dummy()
    app._start_warmup()
    app.floor.root_pulse.assert_called_once_with("playing")
    app._library_page.on_refresh.assert_not_called()
    app._genre_page.on_refresh.assert_not_called()
    app._playlist_page.on_refresh.assert_not_called()


def test_splash_has_no_blocking_anim_budget():
    src = Path(__file__).resolve().parents[1] / "phi" / "ui" / "qt" / "splash.py"
    text = src.read_text(encoding="utf-8")
    assert "_ANIM_MS" not in text
    assert "def start_pulse" in text
    assert "time.sleep" not in text
