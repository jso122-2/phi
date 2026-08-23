#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/rescrape_short.py — re-download tracks that are ~30s Spotify previews.

Usage
-----
    # Dry-run: list what would be rescrapped
    python scripts/rescrape_short.py --dry-run

    # Live rescrape with default 4 workers
    python scripts/rescrape_short.py

    # Faster / slower
    python scripts/rescrape_short.py --workers 2

    # Without VPN proxy
    python scripts/rescrape_short.py --no-proxy

    # Scan a specific directory instead of the phi library
    python scripts/rescrape_short.py --scan ~/Desktop/Spotify

Detection logic
---------------
Spotify's Web API preview_url clips are always 29.5–30.5 seconds.
This script targets the range 28.5–31.0s to capture the whole cluster
while leaving genuinely short tracks (intros, skits < 28s) untouched.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Ensure project root is importable
_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from pipeline.fetcher.models import TrackInfo, Job
from pipeline.sources import DEFAULT_SOURCES
from pipeline.worker.multi_source import download_track

log = logging.getLogger("rescrape")

AUDIO_EXTS   = {".mp3", ".m4a", ".flac", ".ogg", ".opus", ".wav"}
PREVIEW_MIN  = 28.5   # seconds — below this we assume genuine short content
PREVIEW_MAX  = 31.0   # seconds — above this definitely not a preview


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _duration(path: str) -> float | None:
    """Return audio duration in seconds via mutagen, or None on failure."""
    try:
        import mutagen
        f = mutagen.File(path)
        if f is not None and hasattr(f, "info"):
            return f.info.length
    except Exception:
        pass
    return None


def _read_tags(path: str) -> dict:
    """Return basic tag dict (title, artist, album) from an audio file."""
    tags: dict = {"title": None, "artist": None, "album": None}
    try:
        import mutagen
        f = mutagen.File(path, easy=True)
        if f is None:
            return tags
        tags["title"]  = (f.get("title")  or [None])[0]
        tags["artist"] = (f.get("artist") or [None])[0]
        tags["album"]  = (f.get("album")  or [None])[0]
    except Exception:
        pass
    return tags


def _make_track_info(path: str) -> TrackInfo | None:
    """Build a TrackInfo from a file's tags.  Returns None if no title/artist."""
    tags = _read_tags(path)
    # Fallback: derive title from filename stem
    name   = tags["title"]  or Path(path).stem
    artist = tags["artist"] or ""
    album  = tags["album"]  or ""
    if not name:
        return None
    return TrackInfo(
        name        = name,
        artists     = artist,
        album       = album,
        spotify_url = "",   # unknown — source layer searches by title+artist
    )


def _find_phi_library() -> list[str]:
    """Load all track paths from ~/.phi/state.json."""
    state_path = Path.home() / ".phi" / "state.json"
    if not state_path.exists():
        return []
    try:
        data = json.loads(state_path.read_text())
        return [p for p in data.get("playlist", []) if os.path.isfile(p)]
    except Exception as exc:
        log.warning("Could not load phi state.json: %s", exc)
        return []


def _scan_dir(directory: Path) -> list[str]:
    """Return all audio files under *directory*."""
    result = []
    for root, _, files in os.walk(str(directory)):
        for fname in files:
            if Path(fname).suffix.lower() in AUDIO_EXTS:
                result.append(os.path.join(root, fname))
    return result


def _find_short_tracks(paths: list[str]) -> list[tuple[str, float]]:
    """Return (path, duration) for tracks in the Spotify preview range."""
    short = []
    for p in paths:
        dur = _duration(p)
        if dur is not None and PREVIEW_MIN <= dur <= PREVIEW_MAX:
            short.append((p, dur))
    return short


# ---------------------------------------------------------------------------
# Rescrape logic
# ---------------------------------------------------------------------------

def _rescrape_one(
    path:    str,
    proxy:   str | None,
    timeout: int,
) -> tuple[bool, str]:
    """
    Re-download one track and overwrite the original file.

    Returns (ok, message).
    """
    track = _make_track_info(path)
    if track is None:
        return False, "no title/artist in tags — cannot search"

    fmt = Path(path).suffix.lstrip(".").lower() or "mp3"
    if fmt not in {"mp3", "m4a", "flac", "ogg", "opus", "wav"}:
        fmt = "mp3"

    with tempfile.TemporaryDirectory(prefix="rescrape_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        result = download_track(
            track      = track,
            output_dir = tmp_path,
            sources    = DEFAULT_SOURCES,
            fmt        = fmt,
            proxy      = proxy,
            timeout_s  = timeout,
        )
        if not result.ok:
            return False, result.error or "all sources failed"

        # Replace old file with new download
        try:
            shutil.move(result.path, path)
        except Exception as exc:
            return False, f"file replace failed: {exc}"

    return True, f"replaced with {result.source}"


def rescrape(
    paths:    list[str],
    *,
    proxy:    str | None = None,
    timeout:  int        = 300,
    dry_run:  bool       = False,
    workers:  int        = 4,
) -> dict:
    """
    Find and re-download all ~30s preview tracks in *paths*.

    Returns summary dict.
    """
    log.info("Scanning %d tracks for previews (%.1f–%.1fs)…",
             len(paths), PREVIEW_MIN, PREVIEW_MAX)
    short = _find_short_tracks(paths)
    log.info("Found %d preview-length tracks", len(short))

    if not short:
        return {"scanned": len(paths), "previews": 0, "ok": 0, "failed": 0, "skipped": 0}

    if dry_run:
        print(f"\n[dry-run] Would rescrape {len(short)} tracks:")
        for p, dur in sorted(short, key=lambda t: t[1]):
            tags = _read_tags(p)
            artist = tags.get("artist") or "?"
            title  = tags.get("title")  or Path(p).stem
            print(f"  {dur:5.1f}s  {artist} — {title}")
            print(f"          {p}")
        return {"scanned": len(paths), "previews": len(short), "ok": 0, "failed": 0, "skipped": len(short)}

    ok_count   = 0
    fail_count = 0

    if workers > 1:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="rescrape") as pool:
            future_to_path = {
                pool.submit(_rescrape_one, p, proxy, timeout): p
                for p, _ in short
            }
            done = 0
            for future in concurrent.futures.as_completed(future_to_path):
                p = future_to_path[future]
                done += 1
                try:
                    success, msg = future.result()
                except Exception as exc:
                    success, msg = False, str(exc)
                if success:
                    ok_count += 1
                    log.info("[%d/%d] ✓  %s  (%s)", done, len(short), Path(p).name, msg)
                else:
                    fail_count += 1
                    log.warning("[%d/%d] ✗  %s  — %s", done, len(short), Path(p).name, msg)
    else:
        for i, (p, _) in enumerate(short, 1):
            success, msg = _rescrape_one(p, proxy, timeout)
            if success:
                ok_count += 1
                log.info("[%d/%d] ✓  %s  (%s)", i, len(short), Path(p).name, msg)
            else:
                fail_count += 1
                log.warning("[%d/%d] ✗  %s  — %s", i, len(short), Path(p).name, msg)

    return {
        "scanned":  len(paths),
        "previews": len(short),
        "ok":       ok_count,
        "failed":   fail_count,
        "skipped":  0,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog        = "python scripts/rescrape_short.py",
        description = "Re-download ~30s Spotify preview tracks with full-length versions.",
    )
    parser.add_argument(
        "--scan", metavar="DIR",
        help="Scan a directory instead of the phi library (~/.phi/state.json).",
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="List affected tracks without downloading.",
    )
    parser.add_argument(
        "--workers", "-j", type=int, default=4,
        help="Parallel download threads (default: 4).",
    )
    parser.add_argument(
        "--proxy",
        help="SOCKS5 proxy URL e.g. socks5://127.0.0.1:1080 (overrides auto-detect).",
    )
    parser.add_argument(
        "--no-proxy", action="store_true",
        help="Disable proxy even if Mullvad is running.",
    )
    parser.add_argument(
        "--timeout", type=int, default=300,
        help="Per-track yt-dlp timeout in seconds (default: 300).",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level  = getattr(logging, args.log_level),
        format = "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt= "%H:%M:%S",
    )

    # Resolve proxy
    if args.no_proxy:
        proxy = None
    elif args.proxy:
        proxy = args.proxy
    else:
        # Auto-detect: use Mullvad SOCKS5 if the CLI says it's connected
        proxy = None
        try:
            import subprocess
            r = subprocess.run(["mullvad", "status"], capture_output=True, text=True, timeout=3)
            if "Connected" in r.stdout:
                proxy = "socks5://127.0.0.1:1080"
                log.info("Mullvad connected — routing through SOCKS5 proxy")
        except Exception:
            pass

    # Collect paths to scan
    if args.scan:
        scan_dir = Path(args.scan).expanduser().resolve()
        if not scan_dir.is_dir():
            print(f"ERROR: not a directory: {scan_dir}", file=sys.stderr)
            return 1
        log.info("Scanning directory: %s", scan_dir)
        paths = _scan_dir(scan_dir)
    else:
        log.info("Loading phi library from ~/.phi/state.json")
        paths = _find_phi_library()

    if not paths:
        print("No audio files found.")
        return 0

    summary = rescrape(
        paths   = paths,
        proxy   = proxy,
        timeout = args.timeout,
        dry_run = args.dry_run,
        workers = args.workers,
    )

    print(f"\n{'[dry-run] ' if args.dry_run else ''}Summary:")
    print(f"  Scanned : {summary['scanned']}")
    print(f"  Previews: {summary['previews']}")
    if not args.dry_run:
        print(f"  OK      : {summary['ok']}")
        print(f"  Failed  : {summary['failed']}")

    return 0 if summary.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
