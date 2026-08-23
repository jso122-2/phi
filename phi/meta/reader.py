# -*- coding: utf-8 -*-
"""phi.meta.reader — tag reading for any audio format via mutagen.

Primary entry points
--------------------
read_meta(path)                 — full mutagen scan, always reads from disk
read_meta_cached(path, cache)   — checks SQLite cache first, falls back to mutagen
scan_folder_cached(folder, cache) — bulk scan with cache awareness
"""
from __future__ import annotations
import os
from typing import TYPE_CHECKING

import mutagen
from mutagen.id3 import ID3

from phi.config import AUDIO_EXTS

if TYPE_CHECKING:
    from phi.meta.cache import MetaCache


def read_meta_cached(path: str, cache: "MetaCache") -> dict:
    """
    Return metadata for *path*, using the SQLite cache where possible.

    Cache hit  → O(1) SQLite read, no file I/O beyond mtime check.
    Cache miss → full mutagen scan, result stored in cache for next time.

    Always safe to call from any thread.
    """
    hit = cache.get(path)
    if hit is not None:
        return hit
    meta = read_meta(path)
    cache.put(path, meta)
    return meta


def bulk_prime_cache(paths: list[str], cache: "MetaCache") -> dict[str, dict]:
    """
    Efficiently prime the cache for *paths*.

    1. Bulk-fetch all cache-fresh rows in one SQL query.
    2. For any misses, read from disk and store results in the cache.

    Returns {path: meta} for all paths.
    """
    cached = cache.get_many(paths)
    missing = [p for p in paths if p not in cached]

    result = dict(cached)
    for path in missing:
        meta = read_meta(path)
        cache.put(path, meta)
        result[path] = meta

    return result


def read_meta(path: str) -> dict:
    """
    Return a tag dict for the given audio file.
    Always safe to call from any thread. Never raises.

    Keys: title, artist, album, track, year, art_bytes, duration
    """
    m: dict = {
        "title":        None,
        "artist":       None,
        "album":        None,
        "album_artist": None,
        "track":        None,
        "disc_num":     None,
        "year":         None,
        "genre":        None,
        "comment":      None,
        "art_bytes":    None,
        "duration":     None,
        "bpm":          None,
        "key":          None,
        "rg_track_gain": None,   # ReplayGain track gain in dB (float)
        "rg_track_peak": None,   # ReplayGain track peak (float 0-1)
    }

    # ── tags (easy interface works for all formats) ───────────────────────────
    try:
        audio = mutagen.File(path, easy=True)
        if audio:
            def first(key):
                v = audio.get(key)
                return v[0] if v else None

            m["title"]        = first("title")
            m["artist"]       = first("artist")
            m["album"]        = first("album")
            m["album_artist"] = first("albumartist") or first("album_artist")
            m["genre"]        = first("genre")
            m["comment"]      = first("comment") or first("description")
            m["year"]         = str(first("date") or "")[:4] or None

            trk = first("tracknumber")
            if trk:
                try:
                    m["track"] = int(str(trk).split("/")[0])
                except ValueError:
                    pass

            disc = first("discnumber")
            if disc:
                try:
                    m["disc_num"] = int(str(disc).split("/")[0])
                except ValueError:
                    pass

            bpm = first("bpm")
            if bpm:
                try:
                    m["bpm"] = float(bpm)
                except ValueError:
                    pass

            m["key"] = first("initialkey") or first("key")

            # ReplayGain (EasyID3 / Vorbis expose these as lowercase)
            for rg_key in ("replaygain_track_gain", "replaygain_track_gain "):
                rg = first(rg_key)
                if rg:
                    try:
                        m["rg_track_gain"] = float(str(rg).replace("dB", "").strip())
                    except ValueError:
                        pass
                    break
            for rg_key in ("replaygain_track_peak", "replaygain_track_peak "):
                rp = first(rg_key)
                if rp:
                    try:
                        m["rg_track_peak"] = float(str(rp).strip())
                    except ValueError:
                        pass
                    break

            if hasattr(audio, "info") and hasattr(audio.info, "length"):
                m["duration"] = audio.info.length
    except Exception:
        pass

    # ── genre fallback — raw ID3 TCON (catches numeric-only codes) ──────────
    if not m["genre"]:
        try:
            tags = ID3(path)
            tcon = tags.get("TCON")
            if tcon:
                import re as _re
                raw = str(tcon)
                clean = _re.sub(r"^\(\d+\)", "", raw).strip()
                if clean:
                    m["genre"] = clean
        except Exception:
            pass

    # ── genre fallback — MP4 ©gen (belt-and-suspenders) ──────────────────────
    if not m["genre"]:
        try:
            from mutagen.mp4 import MP4
            mp4 = MP4(path)
            gen = mp4.tags.get("\xa9gen") if mp4.tags else None
            if gen:
                m["genre"] = str(gen[0]) if isinstance(gen, list) else str(gen)
        except Exception:
            pass

    # ── embedded art — ID3 (MP3, AAC, AIFF) ──────────────────────────────────
    if not m["art_bytes"]:
        try:
            tags = ID3(path)
            for key in tags:
                if key.startswith("APIC"):
                    m["art_bytes"] = tags[key].data
                    break
        except Exception:
            pass

    # ── embedded art — FLAC ───────────────────────────────────────────────────
    if not m["art_bytes"]:
        try:
            from mutagen.flac import FLAC
            pics = FLAC(path).pictures
            if pics:
                m["art_bytes"] = pics[0].data
        except Exception:
            pass

    # ── fallback — cover image in same folder ─────────────────────────────────
    if not m["art_bytes"]:
        folder = os.path.dirname(path)
        for name in ("cover.jpg", "cover.png", "folder.jpg",
                     "artwork.jpg", "front.jpg"):
            candidate = os.path.join(folder, name)
            if os.path.isfile(candidate):
                try:
                    with open(candidate, "rb") as f:
                        m["art_bytes"] = f.read()
                except Exception:
                    pass
                break

    return m


def track_sort_key(path: str) -> tuple:
    """Return (track_number, basename) so folders sort by track order."""
    try:
        audio = mutagen.File(path, easy=True)
        if audio:
            trk = (audio.get("tracknumber") or [None])[0]
            if trk:
                return (int(str(trk).split("/")[0]), os.path.basename(path))
    except Exception:
        pass
    return (9999, os.path.basename(path))


def scan_folder(folder: str) -> list[str]:
    """Return audio paths in a folder, sorted by track number."""
    paths = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in AUDIO_EXTS
    ]
    paths.sort(key=track_sort_key)
    return paths


def scan_folder_cached(folder: str, cache: "MetaCache") -> dict[str, dict]:
    """
    Scan *folder* and return {path: meta} for all audio files, using the
    SQLite cache for tracks that have not changed since last scan.
    """
    paths = scan_folder(folder)
    return bulk_prime_cache(paths, cache)
