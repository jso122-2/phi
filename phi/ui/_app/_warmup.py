# -*- coding: utf-8 -*-
"""phi.ui._app._warmup — launch stay-light: rooms warm themselves on first show.

Pages already rebuild in on_show() when ``_cache_warm`` is False. Eagerly
refreshing library / genre / playlist at startup was tanker work on the
main thread before the playing page had even painted.
"""
from __future__ import annotations


class _WarmupMixin:
    """Hovercraft warmup — playing hub only. Mixed into PhiMainWindow."""

    def _start_warmup(self) -> None:
        """Pulse the visible hub. Stacked rooms warm on first navigation."""
        floor = getattr(self, "floor", None)
        if floor is not None:
            try:
                floor.root_pulse("playing")
            except Exception:
                pass
