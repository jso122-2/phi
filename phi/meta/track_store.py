# -*- coding: utf-8 -*-
"""phi.meta.track_store — per-track local data store.

Materialises a self-contained directory for every track in the phi library:

    ~/.phi/library/
        _index.json                  # slug ↔ original-path index
        radiohead_creep/
            audio.mp3                # symlink → original file
            meta.json                # file tags (title, artist, album, year…)
            annotations.json         # all enrichment (Spotify, LFM, MB, Discogs, Deezer…)
            features.json            # librosa audio features (BPM, MFCCs, spectral…)
            telemetry.json           # play stats, ELO, engagement heuristics
            lyrics.txt               # plain-text lyrics (if available)
            cover.jpg                # album art (if available)
            spectrogram/             # (optional — written by --spectrograms flag)
                mel_128.npy          # float32 (T, 128) log-mel spectrogram
                chroma_12.npy        # float32 (T, 12) chromagram
                tonnetz_6.npy        # float32 (T, 6)  tonal centroid features

Usage
-----
    # CLI — build store for all library tracks
    python -m phi.meta.track_store

    # Also compute ML spectrograms (CPU-heavy)
    python -m phi.meta.track_store --spectrograms --workers 4

    # From Python
    from phi.meta.track_store import TrackStore
    store = TrackStore()
    store.build_all(spectrograms=False, force=False)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from phi.meta._track_index import _Index, _slugify, _make_slug
from phi.meta._track_helpers import (
    _load_state,
    _load_meta_store,
    _load_annotations_db,
    _load_tag_db,
    _build_telemetry,
    _is_annotation,
    _split_features,
    _json_default,
    _write_json,
    _ANNOTATION_PREFIXES,
    _LIBROSA_FIELDS,
    _META_FIELDS,
)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PHI_DIR    = Path.home() / ".phi"
LIBRARY_DIR = _PHI_DIR / "library"
STATE_FILE  = _PHI_DIR / "state.json"
META_STORE  = _PHI_DIR / "meta_store.jsonl"
META_DB     = _PHI_DIR / "meta.db"
INDEX_FILE  = LIBRARY_DIR / "_index.json"

_HERE = Path(__file__).resolve().parent.parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def build_track_dir(
    *,
    audio_path: str,
    slug: str,
    tag_meta: dict,
    annotation: dict,
    features: dict,
    telemetry: dict,
    force: bool = False,
) -> Path:
    """
    Create (or refresh) the per-track directory for *audio_path*.

    Returns the directory path.
    """
    track_dir = LIBRARY_DIR / slug
    track_dir.mkdir(parents=True, exist_ok=True)

    ext  = Path(audio_path).suffix or ".mp3"
    link = track_dir / f"audio{ext}"

    # ── symlink ───────────────────────────────────────────────────────────────
    if not link.exists() or force:
        try:
            link.unlink(missing_ok=True)
            link.symlink_to(audio_path)
        except Exception:
            pass

    # ── meta.json ─────────────────────────────────────────────────────────────
    meta_out = {k: v for k, v in tag_meta.items() if k != "art_bytes"}
    meta_out["source_path"] = audio_path
    meta_out["slug"]        = slug
    meta_path = track_dir / "meta.json"
    if not meta_path.exists() or force:
        _write_json(meta_path, meta_out)

    # ── annotations.json ──────────────────────────────────────────────────────
    ann_path = track_dir / "annotations.json"
    if annotation and (not ann_path.exists() or force):
        _write_json(ann_path, annotation)

    # ── features.json ─────────────────────────────────────────────────────────
    feat_path = track_dir / "features.json"
    if features and (not feat_path.exists() or force):
        _write_json(feat_path, features)

    # ── telemetry.json ────────────────────────────────────────────────────────
    tel_path = track_dir / "telemetry.json"
    if not tel_path.exists() or force:
        _write_json(tel_path, telemetry)

    # ── lyrics.txt ────────────────────────────────────────────────────────────
    lyrics_text = annotation.get("lyrics_text")
    lyr_path = track_dir / "lyrics.txt"
    if lyrics_text and (not lyr_path.exists() or force):
        lyr_path.write_text(lyrics_text, encoding="utf-8")

    # ── cover.jpg ─────────────────────────────────────────────────────────────
    art_bytes = tag_meta.get("art_bytes")
    # Fall back to annotation bytes if stored separately
    if not art_bytes:
        art_bytes = annotation.get("art_bytes")
    art_path = track_dir / "cover.jpg"
    if art_bytes and isinstance(art_bytes, (bytes, bytearray)) and (
        not art_path.exists() or force
    ):
        try:
            art_path.write_bytes(bytes(art_bytes))
        except Exception:
            pass

    return track_dir


# ---------------------------------------------------------------------------
# Spectrogram worker (subprocess-isolated)
# ---------------------------------------------------------------------------

_SPEC_WORKER = Path(__file__).parent / "_spectrogram_worker.py"
_PYTHON      = sys.executable
_SPEC_TIMEOUT = 60  # seconds


def _compute_spectrograms(track_dir: Path, audio_path: str, force: bool = False) -> bool:
    """
    Spawn _spectrogram_worker.py to compute and save spectrograms for a track.
    Returns True on success.
    """
    spec_dir = track_dir / "spectrogram"
    mel_path = spec_dir / "mel_128.npy"

    if mel_path.exists() and not force:
        return True  # Already computed

    spec_dir.mkdir(exist_ok=True)
    try:
        result = subprocess.run(
            [_PYTHON, str(_SPEC_WORKER), audio_path, str(spec_dir)],
            timeout=_SPEC_TIMEOUT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# TrackStore — main orchestrator
# ---------------------------------------------------------------------------

class TrackStore:
    """
    Builds and maintains ~/.phi/library/ — the per-track local data store.

    Loads all data sources once, then builds individual track directories
    using a thread pool.
    """

    def __init__(
        self,
        library_dir: Path = LIBRARY_DIR,
        state_file:  Path = STATE_FILE,
        meta_store:  Path = META_STORE,
        meta_db:     Path = META_DB,
    ) -> None:
        self._library_dir = library_dir
        self._state_file  = state_file
        self._meta_store  = meta_store
        self._meta_db     = meta_db
        self._index       = _Index(library_dir / "_index.json")

    # ── public API ────────────────────────────────────────────────────────────

    def build_all(
        self,
        *,
        spectrograms: bool = False,
        workers:      int  = 4,
        force:        bool = False,
        verbose:      bool = True,
    ) -> dict[str, Any]:
        """
        Build per-track directories for all library tracks.

        Returns a summary dict with counts.
        """
        self._library_dir.mkdir(parents=True, exist_ok=True)

        if verbose:
            print("Loading data sources…", flush=True)

        state      = _load_state(self._state_file)
        play_stats = state.get("play_stats", {})

        # Collect tracks from all known sources — playlist, play_stats, and
        # meta_store — so the store works even with an empty playlist.
        path_set: set[str] = set()
        path_set.update(p for p in state.get("playlist", []) if os.path.isfile(p))
        path_set.update(p for p in play_stats if os.path.isfile(p))

        # Load meta store now (needed below) and pull its paths too
        features = _load_meta_store(self._meta_store)
        path_set.update(p for p in features if os.path.isfile(p))

        paths = sorted(path_set)

        if not paths:
            print("No tracks found (playlist, play_stats, and meta_store are all empty).", flush=True)
            return {"total": 0}

        features    = _load_meta_store(self._meta_store)
        annotations = _load_annotations_db(self._meta_db)
        tags        = _load_tag_db(self._meta_db)
        # Also pull any paths the annotations DB knows about
        path_set.update(p for p in annotations if os.path.isfile(p))
        path_set.update(p for p in tags if os.path.isfile(p))
        paths = sorted(path_set)

        if verbose:
            print(
                f"Library: {len(paths)} tracks  "
                f"| features: {len(features)}  "
                f"| annotations: {len(annotations)}  "
                f"| tags in DB: {len(tags)}",
                flush=True,
            )

        t0  = time.time()
        ok  = 0
        err = 0
        lock = threading.Lock()

        def _do(path: str) -> tuple[str, bool]:
            try:
                tag_meta   = tags.get(path) or {}
                store_rec  = features.get(path) or {}
                annotation = annotations.get(path) or {}

                # Build meta from tags, falling back to store fields
                if not tag_meta:
                    tag_meta = {
                        k: store_rec.get(k)
                        for k in ("title", "artist", "album", "year", "genre", "duration")
                    }

                feat = _split_features(store_rec)

                duration = (
                    tag_meta.get("duration")
                    or store_rec.get("duration")
                    or 0.0
                )
                raw_stats  = play_stats.get(path, {})
                telemetry  = _build_telemetry(path, raw_stats, float(duration or 0))

                # Resolve slug
                base_slug = _make_slug(tag_meta, path)
                slug      = self._index.register(path, base_slug)

                track_dir = build_track_dir(
                    audio_path = path,
                    slug       = slug,
                    tag_meta   = tag_meta,
                    annotation = annotation,
                    features   = feat,
                    telemetry  = telemetry,
                    force      = force,
                )

                if spectrograms:
                    _compute_spectrograms(track_dir, path, force=force)

                return path, True
            except Exception as exc:
                return path, False

        done = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_do, p): p for p in paths}

            for fut in as_completed(futures):
                _, success = fut.result()
                with lock:
                    if success:
                        ok += 1
                    else:
                        err += 1
                    done += 1
                    _done = done

                if verbose and (_done % 100 == 0 or _done == len(paths)):
                    elapsed = time.time() - t0
                    rate    = _done / elapsed if elapsed > 0 else 0
                    eta     = (len(paths) - _done) / rate if rate > 0 else 0
                    print(
                        f"  {_done}/{len(paths)}  "
                        f"{rate:.0f} t/s  "
                        f"ETA {int(eta // 60)}m{int(eta % 60):02d}s  "
                        f"errors: {err}",
                        flush=True,
                    )

        self._index.save()

        elapsed = time.time() - t0
        if verbose:
            print(f"\n✓ Done in {elapsed:.1f}s")
            print(f"  {ok} tracks written  |  {err} errors")
            print(f"  Store: {self._library_dir}")
            print(f"  Index: {self._library_dir / '_index.json'}")

        return {
            "total":   len(paths),
            "ok":      ok,
            "errors":  err,
            "elapsed": round(elapsed, 1),
            "store":   str(self._library_dir),
        }

    def build_one(self, path: str, *, spectrograms: bool = False, force: bool = False) -> Optional[Path]:
        """Build the directory for a single track path. Returns the dir Path or None on failure."""
        state      = _load_state(self._state_file)
        play_stats = state.get("play_stats", {})
        features   = _load_meta_store(self._meta_store)
        annotations = _load_annotations_db(self._meta_db)
        tags       = _load_tag_db(self._meta_db)

        tag_meta   = tags.get(path) or {}
        store_rec  = features.get(path) or {}
        annotation = annotations.get(path) or {}

        if not tag_meta:
            tag_meta = {k: store_rec.get(k)
                        for k in ("title", "artist", "album", "year", "genre", "duration")}

        feat      = _split_features(store_rec)
        duration  = tag_meta.get("duration") or store_rec.get("duration") or 0.0
        telemetry = _build_telemetry(path, play_stats.get(path, {}), float(duration))

        base_slug = _make_slug(tag_meta, path)
        slug      = self._index.register(path, base_slug)

        try:
            track_dir = build_track_dir(
                audio_path = path,
                slug       = slug,
                tag_meta   = tag_meta,
                annotation = annotation,
                features   = feat,
                telemetry  = telemetry,
                force      = force,
            )
            if spectrograms:
                _compute_spectrograms(track_dir, path, force=force)
            self._index.save()
            return track_dir
        except Exception:
            return None

    def refresh_telemetry(self, verbose: bool = True) -> int:
        """
        Re-write only telemetry.json for all tracks in the index.
        Fast — does not touch audio or metadata files.
        """
        state      = _load_state(self._state_file)
        play_stats = state.get("play_stats", {})
        features   = _load_meta_store(self._meta_store)
        tags       = _load_tag_db(self._meta_db)

        updated = 0
        for path, slug in self._index._path_to_slug.items():
            track_dir = self._library_dir / slug
            if not track_dir.exists():
                continue
            tag_meta = tags.get(path) or {}
            store_rec = features.get(path) or {}
            duration = (tag_meta.get("duration") or store_rec.get("duration") or 0.0)
            telemetry = _build_telemetry(path, play_stats.get(path, {}), float(duration))
            try:
                _write_json(track_dir / "telemetry.json", telemetry)
                updated += 1
            except Exception:
                pass

        if verbose:
            print(f"Refreshed telemetry for {updated} tracks.", flush=True)
        return updated

    def prune(self, verbose: bool = True) -> int:
        """
        Remove track directories for paths no longer in the library.
        """
        state   = _load_state(self._state_file)
        current = set(state.get("playlist", []))
        removed = 0

        for path, slug in list(self._index._path_to_slug.items()):
            if path not in current:
                track_dir = self._library_dir / slug
                if track_dir.exists():
                    shutil.rmtree(track_dir, ignore_errors=True)
                self._index.remove(path)
                removed += 1

        if removed:
            self._index.save()

        if verbose:
            print(f"Pruned {removed} stale track directories.", flush=True)
        return removed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m phi.meta.track_store",
        description=(
            "Build the per-track local data store at ~/.phi/library/.\n"
            "Each track gets its own directory with metadata, features, "
            "telemetry, lyrics, and album art."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--spectrograms", "-S", action="store_true",
        help="Also compute mel spectrogram + chromagram (CPU-heavy, ~5–15s per track)",
    )
    parser.add_argument(
        "--workers", "-j", type=int, default=4,
        help="Parallel workers (default: 4)",
    )
    parser.add_argument(
        "--force", "-f", action="store_true",
        help="Re-write all files even if they already exist",
    )
    parser.add_argument(
        "--refresh-telemetry", action="store_true",
        help="Only refresh telemetry.json for all tracks (fast)",
    )
    parser.add_argument(
        "--prune", action="store_true",
        help="Remove directories for tracks no longer in the library",
    )
    parser.add_argument(
        "--one", metavar="PATH",
        help="Build the directory for a single track path",
    )
    args = parser.parse_args(argv)

    store = TrackStore()

    if args.one:
        result = store.build_one(
            args.one,
            spectrograms=args.spectrograms,
            force=args.force,
        )
        if result:
            print(f"✓ {result}", flush=True)
        else:
            print("✗ Failed to build track directory.", file=sys.stderr, flush=True)
            sys.exit(1)
        return

    if args.refresh_telemetry:
        store.refresh_telemetry()
        return

    if args.prune:
        store.prune()
        return

    store.build_all(
        spectrograms=args.spectrograms,
        workers=args.workers,
        force=args.force,
    )


if __name__ == "__main__":
    main()
