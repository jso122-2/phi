#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/train_d4.py — D4 XGBoost baseline training script.

Pulls all track metadata from ~/.phi/meta.db, runs GeminiClipper to produce
dragon curve features, fits D4XGBoostModel, and saves to ~/.phi/d4_xgb.joblib.

The phi app auto-loads the checkpoint on next startup.

Usage:
    python scripts/train_d4.py
    python scripts/train_d4.py --batch-size 32 --depth 8 --window 16
    python scripts/train_d4.py --skip-existing     # resume interrupted run
    python scripts/train_d4.py --dry-run           # annotate only, don't fit
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("train_d4")

# ── paths ─────────────────────────────────────────────────────────────────────

PHI_DIR  = Path.home() / ".phi"
META_DB  = PHI_DIR / "meta.db"
D4_CKPT  = PHI_DIR / "d4_xgb.joblib"
HEAD_CKPT = PHI_DIR / "gemini_head.pt"


# ── DB helpers ────────────────────────────────────────────────────────────────

def _load_tracks(db_path: Path) -> list[tuple[str, dict]]:
    """
    Return all (path, meta) pairs from the tracks table.
    Skips paths whose files no longer exist on disk.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT path, title, artist, album, genre, bpm, key_sig, duration "
        "FROM tracks ORDER BY artist, album, path"
    ).fetchall()
    conn.close()

    items: list[tuple[str, dict]] = []
    missing = 0
    for row in rows:
        p = row["path"]
        if not Path(p).exists():
            missing += 1
            continue
        items.append((
            p,
            {
                "title":    row["title"],
                "artist":   row["artist"],
                "album":    row["album"],
                "genre":    row["genre"],
                "bpm":      row["bpm"],
                "key":      row["key_sig"],
                "duration": row["duration"],
            },
        ))
    if missing:
        log.warning("skipped %d tracks — files not found on disk", missing)
    return items


def _load_existing_annotations(db_path: Path, paths: list[str]) -> dict[str, dict]:
    """Bulk-load existing annotation dicts from the annotations table."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    if not paths:
        conn.close()
        return {}
    placeholders = ",".join("?" * len(paths))
    rows = conn.execute(
        f"SELECT path, data FROM annotations WHERE path IN ({placeholders})",
        paths,
    ).fetchall()
    conn.close()
    result: dict[str, dict] = {}
    for row in rows:
        try:
            result[row["path"]] = json.loads(row["data"])
        except Exception:
            pass
    return result


def _save_annotations(db_path: Path, annotations: dict[str, dict]) -> None:
    """Bulk upsert annotation dicts to the annotations table."""
    from datetime import datetime
    now = datetime.now().isoformat()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    def _default(obj):
        if hasattr(obj, "tolist"):
            return obj.tolist()
        if hasattr(obj, "item"):
            return obj.item()
        raise TypeError(type(obj))

    rows = [
        (path, json.dumps(ann, default=_default), now)
        for path, ann in annotations.items()
        if ann
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO annotations (path, data, updated_at) VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


# ── annotation phase ──────────────────────────────────────────────────────────

def annotate(
    items: list[tuple[str, dict]],
    existing: dict[str, dict],
    batch_size: int,
    depth: int,
    skip_existing: bool,
    window: int = 16,
) -> tuple[list[dict], np.ndarray]:
    """
    Run MetaClipper over all items, using cached annotations where possible.

    Returns:
        annotations:  list of annotation dicts (one per item, same order)
        rolling_d4a:  ndarray shape (N,) — causal rolling mean of D4_A
    """
    from phi.models.meta_clipper import MetaClipper

    clipper = MetaClipper(depth=depth, device="cpu")
    all_anns: list[dict] = []

    # Identify which items need processing
    to_process_idx: list[int] = []
    for i, (path, _) in enumerate(items):
        ann = existing.get(path, {})
        if skip_existing and ann.get("clipper_emb") is not None:
            all_anns.append(ann)
        else:
            all_anns.append({})
            to_process_idx.append(i)

    if not to_process_idx:
        log.info("all %d tracks already annotated — using cache", len(items))
    else:
        log.info(
            "annotating %d tracks  (cached: %d)  batch_size=%d",
            len(to_process_idx), len(items) - len(to_process_idx), batch_size,
        )
        try:
            from tqdm import tqdm  # type: ignore[import]
            _tqdm = tqdm
        except ImportError:
            _tqdm = None

        # Fit the clipper on the FULL library corpus so the TF-IDF vocabulary
        # covers all tracks, not just the first batch.
        log.info("fitting MetaClipper on %d tracks…", len(items))
        clipper.fit(items)

        batches = [
            to_process_idx[i : i + batch_size]
            for i in range(0, len(to_process_idx), batch_size)
        ]
        it = _tqdm(batches, unit="batch") if _tqdm else batches

        new_annotations: dict[str, dict] = {}
        t0 = time.time()

        for batch_indices in it:
            batch_items = [items[i] for i in batch_indices]
            batch_anns, _ = clipper.run_batch(batch_items, rolling_window=window)
            for local_i, global_i in enumerate(batch_indices):
                ann = batch_anns[local_i]
                all_anns[global_i] = ann
                path = items[global_i][0]
                # Merge with any existing annotations so we don't wipe prior data
                merged = {**existing.get(path, {}), **ann}
                new_annotations[path] = merged

            # Flush to DB every batch — makes the run resumable
            _save_annotations(META_DB, new_annotations)
            new_annotations.clear()

        elapsed = time.time() - t0
        n_proc = len(to_process_idx)
        log.info(
            "annotation done: %d tracks in %.1fs  (%.2f s/track)",
            n_proc, elapsed, elapsed / max(n_proc, 1),
        )

    # Compute rolling D4_A over ALL items (including cached) to get stable target
    from phi.models.dragon_curve import DragonCurve
    dc = DragonCurve(depth=depth)
    xy = np.array([
        [ann.get("clipper_x", 0.5), ann.get("clipper_y", 0.5)]
        for ann in all_anns
    ], dtype=np.float64)
    rolling_d4a = dc.rolling_d4_a(xy, window=16, normalized=True)
    log.info(
        "rolling D4_A stats: mean=%.4f  std=%.4f  min=%.4f  max=%.4f",
        rolling_d4a.mean(), rolling_d4a.std(), rolling_d4a.min(), rolling_d4a.max(),
    )

    return all_anns, rolling_d4a


# ── training phase ────────────────────────────────────────────────────────────

def fit_model(
    annotations: list[dict],
    rolling_d4a: np.ndarray,
    xgb_params: dict | None = None,
) -> None:
    """Fit D4XGBoostModel and save checkpoint to ~/.phi/d4_xgb.joblib."""
    from phi.models.d4_model import D4XGBoostModel

    model = D4XGBoostModel(xgb_params=xgb_params)
    log.info("fitting XGBoost on %d samples…", len(annotations))
    t0 = time.time()
    stats = model.fit(annotations, rolling_d4a)
    elapsed = time.time() - t0

    log.info(
        "fit done in %.1fs:  n_train=%d  n_val=%d  val_rmse=%.6f",
        elapsed, stats["n_train"], stats["n_val"], stats["val_rmse"],
    )

    fi = model.feature_importance()
    log.info(
        "feature importance:  emb_mean=%.4f  fold_mean=%.4f  d4b=%.4f",
        fi["emb_mean"], fi["fold_mean"], fi["d4b_score"],
    )

    model.save(D4_CKPT)
    log.info("checkpoint saved → %s", D4_CKPT)


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Train the D4 XGBoost baseline model")
    parser.add_argument("--batch-size",    type=int,   default=64,
                        help="BERT batch size (default 64)")
    parser.add_argument("--depth",         type=int,   default=8,
                        help="Dragon curve depth (default 8 → 256 segments)")
    parser.add_argument("--window",        type=int,   default=16,
                        help="Rolling D4_A window size (default 16)")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip tracks that already have clipper_emb in DB")
    parser.add_argument("--dry-run",       action="store_true",
                        help="Annotate only — skip XGBoost fitting")
    parser.add_argument("--n-estimators",  type=int,   default=400)
    parser.add_argument("--max-depth",     type=int,   default=6)
    parser.add_argument("--lr",            type=float, default=0.05)
    args = parser.parse_args()

    if not META_DB.exists():
        log.error("meta.db not found at %s — open phi first to populate it", META_DB)
        sys.exit(1)

    # ── 1. load ────────────────────────────────────────────────────────────────
    log.info("loading tracks from %s", META_DB)
    items = _load_tracks(META_DB)
    log.info("%d tracks found on disk", len(items))

    if len(items) < 10:
        log.error("too few tracks (%d) — need at least 10 to train", len(items))
        sys.exit(1)

    paths = [p for p, _ in items]
    existing = _load_existing_annotations(META_DB, paths)
    log.info("%d existing annotations loaded from DB", len(existing))

    # ── 2. annotate ────────────────────────────────────────────────────────────
    annotations, rolling_d4a = annotate(
        items,
        existing,
        batch_size=args.batch_size,
        depth=args.depth,
        skip_existing=args.skip_existing,
        window=args.window,
    )

    valid = sum(1 for a in annotations if a.get("clipper_emb") is not None)
    log.info("%d / %d tracks have valid clipper annotations", valid, len(annotations))

    if args.dry_run:
        log.info("--dry-run: skipping XGBoost fit")
        return

    if valid < 10:
        log.error("not enough valid annotations (%d) to fit model", valid)
        sys.exit(1)

    # ── 3. fit ─────────────────────────────────────────────────────────────────
    xgb_params = {
        "n_estimators":     args.n_estimators,
        "max_depth":        args.max_depth,
        "learning_rate":    args.lr,
        "subsample":        0.8,
        "colsample_bytree": 0.8,
        "reg_alpha":        0.1,
        "reg_lambda":       1.0,
        "objective":        "reg:squarederror",
        "n_jobs":           -1,
        "random_state":     42,
    }
    fit_model(annotations, rolling_d4a, xgb_params=xgb_params)
    log.info("done — restart phi to activate D4 inference")


if __name__ == "__main__":
    main()
