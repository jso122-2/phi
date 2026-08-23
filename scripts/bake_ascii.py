#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
scripts/bake_ascii.py — one-shot batch bake for coloured ASCII album art.

Reads every track row in ~/.phi/meta.db that has art_bytes, converts each
unique image to a coloured ASCII grid, and writes it to:

    ~/.phi/ascii/<sha1[:2]>/<sha1[2:]>_64x32.json

Idempotent — already-baked files are skipped, not re-converted.
Requires only PIL (no Tk, no pygame, no objc).

Usage
-----
    cd /path/to/Spotify-rip
    mamba activate spotify-rip
    python scripts/bake_ascii.py

    # or point at a different DB:
    python scripts/bake_ascii.py --db /path/to/meta.db
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sqlite3
import sys
from pathlib import Path


# ── resolve ~/.phi defaults without importing phi.config ─────────────────────
_DEFAULT_DB  = Path.home() / ".phi" / "meta.db"
_ASCII_ROOT  = Path.home() / ".phi" / "ascii"
_BAKE_COLS   = 64
_BAKE_ROWS   = 32


def _bake_path(digest: str) -> Path:
    return _ASCII_ROOT / digest[:2] / f"{digest[2:]}_{_BAKE_COLS}x{_BAKE_ROWS}.json"


def _bake(art_bytes: bytes) -> bool:
    """Convert art_bytes → JSON grid.  Returns True on success."""
    try:
        from PIL import Image
    except ImportError:
        print("ERROR: Pillow is not installed. Run: mamba install -c conda-forge pillow")
        sys.exit(1)

    try:
        ramp     = " ·:+=ox%#@█"
        ramp_len = len(ramp)

        img_rgb  = Image.open(io.BytesIO(art_bytes)).convert("RGB")
        img_rgb  = img_rgb.resize((_BAKE_COLS, _BAKE_ROWS), Image.LANCZOS)
        img_gray = img_rgb.convert("L")
        pix_rgb  = img_rgb.load()
        pix_gray = img_gray.load()

        grid: list[list[list[str]]] = []
        for r in range(_BAKE_ROWS):
            row: list[list[str]] = []
            for c in range(_BAKE_COLS):
                brightness = pix_gray[c, r]
                char  = ramp[int(brightness / 255 * (ramp_len - 1))]
                rv, gv, bv = pix_rgb[c, r]
                row.append([char, f"#{rv:02x}{gv:02x}{bv:02x}"])
            grid.append(row)

        digest = hashlib.sha1(art_bytes).hexdigest()
        path   = _bake_path(digest)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(grid, fh, separators=(",", ":"))
        return True
    except Exception as exc:
        print(f"\n  bake error: {exc}", file=sys.stderr)
        return False


def run(db_path: Path) -> None:
    if not db_path.exists():
        print(f"ERROR: meta.db not found at {db_path}")
        print("       Run phi at least once to build the database.")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    seen:    set[str] = set()
    total = baked = skipped = errors = 0

    print(f"Reading art from {db_path} …")
    cur = conn.execute(
        "SELECT path, art_bytes FROM tracks WHERE art_bytes IS NOT NULL"
    )

    while True:
        row = cur.fetchone()
        if row is None:
            break

        art_bytes: bytes = row["art_bytes"]
        digest = hashlib.sha1(art_bytes).hexdigest()

        if digest in seen:
            continue
        seen.add(digest)
        total += 1

        if _bake_path(digest).exists():
            skipped += 1
        else:
            if _bake(art_bytes):
                baked += 1
            else:
                errors += 1

        print(
            f"\r  {total} images — {baked} baked  {skipped} cached  {errors} errors",
            end="",
            flush=True,
        )

    conn.close()
    print()   # newline after \r run
    print(
        f"\nDone — {total} unique images: "
        f"{baked} baked, {skipped} already cached, {errors} errors."
    )
    print(f"Cache written to: {_ASCII_ROOT}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=_DEFAULT_DB,
        metavar="PATH",
        help=f"Path to meta.db (default: {_DEFAULT_DB})",
    )
    args = parser.parse_args()
    run(args.db)


if __name__ == "__main__":
    main()
