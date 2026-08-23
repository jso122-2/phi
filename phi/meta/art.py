# -*- coding: utf-8 -*-
"""phi.meta.art — album art extraction, PIL → PhotoImage, and ASCII rendering.

IMPORTANT: make_photo() must only be called from the main (Tk) thread,
as ImageTk.PhotoImage is a Tk resource.

Pre-baked ASCII cache
---------------------
ascii_bake(art_bytes) converts art to the canonical coloured grid and writes
it to ~/.phi/ascii/<sha1[:2]>/<sha1[2:]>_64x32.json.  One file per unique
image — albums shared across tracks hash to the same file.

ascii_load(art_bytes) reads the cached file and returns the grid, or None on
a cache miss.  A JSON stat + read of ~28 KB is effectively free on the main
thread; the expensive PIL path is never touched for cached art.
"""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path

from PIL import Image, ImageTk

# Canonical bake dimensions.  Pre-baked grids are always stored at this size.
BAKE_COLS: int = 64
BAKE_ROWS: int = 32

# Light-to-dark ASCII ramp (index 0 = empty/dark, -1 = full/bright).
# Designed for dark backgrounds: high pixel brightness → dense character.
_RAMP = " ·:+=ox%#@█"
_RAMP_LEN = len(_RAMP)


def make_photo(art_bytes: bytes, size: int) -> ImageTk.PhotoImage | None:
    """
    Convert raw image bytes to a square tkinter PhotoImage.
    Returns None on any failure.
    """
    try:
        img = Image.open(io.BytesIO(art_bytes)).convert("RGB")
        img = img.resize((size, size), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


def art_to_ascii(art_bytes: bytes, cols: int = 36, rows: int = 18) -> str | None:
    """
    Convert raw image bytes to a multi-line ASCII art string (monochrome).

    Resizes the image to *cols* × *rows*, converts to grayscale, then maps
    each pixel's brightness to a character in ``_RAMP``.  Bright pixels →
    dense characters; dark pixels → spaces — correct for dark UI backgrounds.

    Returns ``None`` on any failure (missing bytes, corrupt image, no PIL).
    """
    try:
        img = Image.open(io.BytesIO(art_bytes)).convert("L")
        img = img.resize((cols, rows), Image.LANCZOS)
        pixels = img.load()
        lines: list[str] = []
        for r in range(rows):
            row = "".join(
                _RAMP[int(pixels[c, r] / 255 * (_RAMP_LEN - 1))]
                for c in range(cols)
            )
            lines.append(row)
        return "\n".join(lines)
    except Exception:
        return None


def art_to_ascii_colored(
    art_bytes: bytes,
    cols: int = BAKE_COLS,
    rows: int = BAKE_ROWS,
) -> list[list[tuple[str, str]]] | None:
    """
    Convert raw image bytes to a 2D colour-ASCII grid.

    Each cell is ``(char, "#rrggbb")`` — the character is chosen from
    ``_RAMP`` by grayscale brightness; the colour comes from the original
    RGB pixel so each character renders in the full spectrum of the cover art.

    Returns ``None`` on any failure.
    """
    try:
        img_rgb  = Image.open(io.BytesIO(art_bytes)).convert("RGB")
        img_rgb  = img_rgb.resize((cols, rows), Image.LANCZOS)
        img_gray = img_rgb.convert("L")
        pix_rgb  = img_rgb.load()
        pix_gray = img_gray.load()
        grid: list[list[tuple[str, str]]] = []
        for r in range(rows):
            row: list[tuple[str, str]] = []
            for c in range(cols):
                brightness = pix_gray[c, r]
                char  = _RAMP[int(brightness / 255 * (_RAMP_LEN - 1))]
                rv, gv, bv = pix_rgb[c, r]
                color = f"#{rv:02x}{gv:02x}{bv:02x}"
                row.append((char, color))
            grid.append(row)
        return grid
    except Exception:
        return None


# ── pre-baked ASCII cache ─────────────────────────────────────────────────────

def _ascii_cache_root() -> Path:
    """Return ~/.phi/ascii, creating it if absent.  Lazy import avoids cycles."""
    from phi.config import PHI_DIR  # noqa: PLC0415
    root = PHI_DIR / "ascii"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _bake_path(art_bytes: bytes) -> Path:
    """Derive the canonical cache path from a SHA-1 of the raw art bytes."""
    digest = hashlib.sha1(art_bytes).hexdigest()
    return _ascii_cache_root() / digest[:2] / f"{digest[2:]}_{BAKE_COLS}x{BAKE_ROWS}.json"


def ascii_bake(art_bytes: bytes) -> Path | None:
    """
    Convert *art_bytes* to a coloured ASCII grid at canonical size and persist
    it to ``~/.phi/ascii/<sha1[:2]>/<sha1[2:]>_64x32.json``.

    Idempotent — returns the existing path immediately if the file is already
    present (no re-conversion).  Safe to call from any thread.

    Returns the cache path on success, ``None`` on any failure.
    """
    try:
        path = _bake_path(art_bytes)
        if path.exists():
            return path
        grid = art_to_ascii_colored(art_bytes, BAKE_COLS, BAKE_ROWS)
        if grid is None:
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [[list(cell) for cell in row] for row in grid]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, separators=(",", ":"))
        return path
    except Exception:
        return None


def ascii_load(art_bytes: bytes) -> list[list[tuple[str, str]]] | None:
    """
    Load the pre-baked coloured ASCII grid for *art_bytes*.

    Returns the grid (list of rows, each row a list of ``(char, "#rrggbb")``
    tuples) on a cache hit, ``None`` on a miss or any error.

    Suitable for main-thread calls — a JSON stat + ~28 KB read is effectively
    free and does not touch PIL.
    """
    try:
        path = _bake_path(art_bytes)
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        return [[(cell[0], cell[1]) for cell in row] for row in raw]
    except Exception:
        return None


def ascii_bake_all(db_path: Path | None = None, *, progress: bool = False) -> dict:
    """
    Batch-bake coloured ASCII grids for every track in the metadata DB that
    has art but whose bake file does not yet exist.

    Safe to run at any time — idempotent, never re-bakes an existing file.

    Parameters
    ----------
    db_path : Path | None
        Path to ``meta.db``.  Defaults to ``~/.phi/meta.db``.
    progress : bool
        If True, print a running count to stdout.

    Returns
    -------
    dict with keys ``total``, ``baked``, ``skipped`` (already existed),
    ``errors``.
    """
    from phi.config import META_DB  # noqa: PLC0415
    from phi.meta.cache import MetaCache  # noqa: PLC0415

    target = Path(db_path) if db_path else META_DB
    cache  = MetaCache(target)
    seen:    set[str] = set()   # deduplicate by SHA-1 — one bake per image
    total = baked = skipped = errors = 0

    try:
        for _path, art_bytes in cache.iter_art_bytes():
            digest = hashlib.sha1(art_bytes).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            total += 1
            bake_p = _bake_path(art_bytes)
            if bake_p.exists():
                skipped += 1
            else:
                result = ascii_bake(art_bytes)
                if result is not None:
                    baked += 1
                else:
                    errors += 1
            if progress:
                print(f"\r  baked {baked}  skipped {skipped}  errors {errors}  / {total}", end="", flush=True)
    finally:
        cache.close()

    if progress:
        print()   # newline after \r run

    return {"total": total, "baked": baked, "skipped": skipped, "errors": errors}
