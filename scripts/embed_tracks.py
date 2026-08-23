#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""embed_tracks.py — pre-compute 512-d MetadataEncoder embeddings for phi tracks.

Scans the library for audio files that do not yet have a <track>.npy sidecar
and generates embeddings using the pure-numpy MetadataEncoder (no GPU, no CLAP
model required).  Once saved, phi._loader picks them up automatically on next
library scan and CLAPProjection uses them as Tier-1 input.

Usage
-----
    python scripts/embed_tracks.py                    # watch + fill continuously
    python scripts/embed_tracks.py --once             # one pass then exit
    python scripts/embed_tracks.py --root /path       # override library root
    python scripts/embed_tracks.py --dry-run          # print paths, no writes
    python scripts/embed_tracks.py --workers 4        # parallel workers (default 2)

Output
------
    <track_audio_path>.npy  (float32, shape (512,))
    Written alongside the audio file so phi._loader.clap_npy resolves it.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

# ── resolve project root so the script works from any cwd ─────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from phi._loader import _load_track
from phi._track import Track
from phi.config import AUDIO_EXTS, load_phi_config
from phi.models._metadata_encoder import MetadataEncoder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("embed_tracks")

# ── helpers ───────────────────────────────────────────────────────────────────

def _library_root(cli_root: str | None) -> Path:
    if cli_root:
        return Path(cli_root).expanduser().resolve()
    cfg = load_phi_config()
    root = cfg.get("library_root") or cfg.get("music_root")
    if root:
        return Path(root).expanduser().resolve()
    # last-resort: check phi_config.yaml manually
    raise SystemExit(
        "No library root found.  "
        "Pass --root /path/to/music or set library_root in phi_config.yaml."
    )


def _scan_missing(root: Path) -> list[Path]:
    """Return audio paths that have no .npy sidecar."""
    missing: list[Path] = []
    for audio in root.rglob("*"):
        if audio.suffix.lower() not in AUDIO_EXTS:
            continue
        npy = audio.with_suffix(".npy")
        if not npy.exists():
            missing.append(audio)
    return missing


def _embed_one(audio: Path, encoder: MetadataEncoder, dry_run: bool) -> str:
    """Encode one track and write its .npy sidecar.  Returns a status string."""
    json_path = audio.with_suffix(".json")
    if not json_path.exists():
        # Construct a minimal Track from path only — encoder gracefully handles missing fields
        track = Track(path=audio, json_path=json_path)
    else:
        track = _load_track(audio, json_path)

    vec = encoder.encode_one(track).astype(np.float32)   # (512,) float32
    assert vec.shape == (512,), f"Unexpected shape {vec.shape} for {audio.name}"

    npy_path = audio.with_suffix(".npy")
    if not dry_run:
        np.save(str(npy_path), vec)
        return f"wrote  {npy_path.name}"
    return f"dry    {npy_path.name}"


# ── main loop ─────────────────────────────────────────────────────────────────

def run_pass(root: Path, encoder: MetadataEncoder, dry_run: bool, workers: int) -> int:
    """Embed all missing tracks in root.  Returns number processed."""
    missing = _scan_missing(root)
    if not missing:
        return 0

    log.info("Found %d tracks without .npy sidecar — starting embed pass", len(missing))
    done = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_embed_one, p, encoder, dry_run): p for p in missing}
        for fut in as_completed(futures):
            audio = futures[fut]
            try:
                msg = fut.result()
                log.info("%s", msg)
                done += 1
            except Exception as exc:
                log.warning("FAIL  %s — %s", audio.name, exc)
                errors += 1

    log.info("Pass complete: %d embedded, %d errors", done, errors)
    return done


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root",    help="Library root directory (overrides phi_config.yaml)")
    ap.add_argument("--once",    action="store_true", help="Single pass then exit")
    ap.add_argument("--dry-run", action="store_true", help="Print paths, no writes")
    ap.add_argument("--workers", type=int, default=2,  help="Parallel workers (default 2)")
    ap.add_argument("--interval", type=int, default=300, help="Watch interval in seconds (default 300)")
    args = ap.parse_args()

    root    = _library_root(args.root)
    encoder = MetadataEncoder()
    log.info("Library root: %s", root)
    log.info("Mode: %s", "once" if args.once else f"watch every {args.interval}s")

    if args.once:
        run_pass(root, encoder, args.dry_run, args.workers)
        return

    while True:
        try:
            run_pass(root, encoder, args.dry_run, args.workers)
        except KeyboardInterrupt:
            log.info("Interrupted — exiting")
            break
        except Exception as exc:
            log.error("Pass failed: %s", exc, exc_info=True)

        log.info("Sleeping %ds before next scan …", args.interval)
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            log.info("Interrupted — exiting")
            break


if __name__ == "__main__":
    main()
