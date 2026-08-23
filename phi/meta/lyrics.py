# -*- coding: utf-8 -*-
"""phi.meta.lyrics — lyrics retrieval.

Two sources tried in order:
  1. Embedded in the audio file  (ID3 USLT, Vorbis LYRICS / UNSYNCEDLYRICS)
  2. lrclib.net public API        (no key, generous rate-limits)

Returns plain text with timestamps stripped.
Safe to call from any thread.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request


# ── embedded lyrics ───────────────────────────────────────────────────────────

def read_embedded(path: str) -> str | None:
    """Read lyrics embedded in audio tags.  Returns None on any failure."""
    try:
        from mutagen import File as MFile
        audio = MFile(path, easy=False)
        if audio is None:
            return None

        tags = getattr(audio, "tags", None) or {}

        # ID3 (MP3 / AIFF / …) — USLT frames
        for key in list(tags):
            if key.startswith("USLT"):
                txt = tags[key].text
                if txt and txt.strip():
                    return txt.strip()

        # Vorbis / FLAC / Ogg
        for name in ("LYRICS", "UNSYNCEDLYRICS", "lyrics", "unsyncedlyrics"):
            val = audio.get(name)
            if val:
                return str(val[0]).strip() or None

        return None
    except Exception:
        return None


# ── lrclib.net API ────────────────────────────────────────────────────────────

_LRCLIB = "https://lrclib.net/api/get"
_TIMEOUT = 8


def _strip_timestamps(lrc: str) -> str:
    """Remove [mm:ss.xx] LRC timestamp tags and return plain text."""
    lines = []
    for line in lrc.splitlines():
        clean = re.sub(r"^\[[\d:.]+\]", "", line).strip()
        if clean:
            lines.append(clean)
    return "\n".join(lines)


def fetch_lrclib(
    title: str,
    artist: str,
    album: str = "",
    duration: float = 0.0,
) -> str | None:
    """Fetch from lrclib.net.  Returns plain text or None."""
    params: dict[str, str] = {
        "track_name":  title or "",
        "artist_name": artist or "",
    }
    if album:
        params["album_name"] = album
    if duration > 1:
        params["duration"] = str(int(duration))

    url = _LRCLIB + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "phi/1.0 (local music player)"}
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())

        synced = (data.get("syncedLyrics") or "").strip()
        plain  = (data.get("plainLyrics")  or "").strip()

        if synced:
            return _strip_timestamps(synced)
        if plain:
            return plain
        return None
    except Exception:
        return None


# ── unified entry point ───────────────────────────────────────────────────────

def get_lyrics(path: str, meta: dict | None) -> str | None:
    """
    Return lyrics for *path*.  Tries embedded tags first, then lrclib.net.

    Parameters
    ----------
    path   Absolute audio path.
    meta   Track metadata dict (title, artist, album, duration).

    Returns plain text string or None if nothing was found.
    """
    embedded = read_embedded(path)
    if embedded:
        return embedded

    if not meta:
        return None

    title  = (meta.get("title")  or "").strip()
    artist = (meta.get("artist") or "").strip()
    album  = (meta.get("album")  or "").strip()
    dur    =  meta.get("duration") or 0.0

    if not (title or artist):
        return None

    return fetch_lrclib(title, artist, album, dur)
