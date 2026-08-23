# -*- coding: utf-8 -*-
"""phi.watch.notify — macOS track-change banners.

Sends a macOS notification when a new track starts playing.
Falls back silently on non-macOS or when permission is denied.

Two backend attempts in order:
  1. pync (wrapper around terminal-notifier) — richest: icon + group
  2. osascript AppleScript display notification — no extra deps

Usage
-----
    from phi.watch.notify import notify_track_change
    notify_track_change(title="Shine On", artist="Pink Floyd", album="WYWH")
"""
from __future__ import annotations

import subprocess
import threading


def notify_track_change(
    title:  str = "",
    artist: str = "",
    album:  str = "",
) -> None:
    """
    Send a macOS notification for a track change.

    Non-blocking — fires a daemon thread and returns immediately.
    Silently does nothing if notifications aren't available.
    """
    if not (title or artist):
        return
    threading.Thread(
        target=_send,
        args=(title, artist, album),
        daemon=True,
    ).start()


def _send(title: str, artist: str, album: str) -> None:
    subtitle = artist or album or ""
    body     = album if (artist and album) else ""

    # ── try pync (terminal-notifier) ─────────────────────────────────────────
    try:
        import pync
        pync.notify(
            subtitle or title,
            title   = "phi",
            message = body or subtitle or title,
            group   = "phi",
        )
        return
    except (ImportError, Exception):
        pass

    # ── fallback: osascript ───────────────────────────────────────────────────
    try:
        lines = [f'display notification "{_esc(body or subtitle)}"']
        lines.append(f'with title "phi"')
        if subtitle:
            lines.append(f'subtitle "{_esc(subtitle)}"')
        script = " ".join(lines)
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=3,
        )
    except Exception:
        pass


def _esc(s: str) -> str:
    """Escape quotes for AppleScript string literals."""
    return s.replace("\\", "\\\\").replace('"', '\\"')
