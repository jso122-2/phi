# -*- coding: utf-8 -*-
"""phi.meta.spotify_bulk_enrich — batch Spotify enrichment for the phi library.

Iterates every track that has never been attempted for Spotify enrichment
(spotify_enriched is NULL in annotations) and enriches it using:

  1. ISRC exact-match lookup  (if isrc is already stored in annotations)
  2. title + artist fuzzy search  (fallback)

Results are written directly to ~/.phi/meta.db annotations — no phi app
instance required.  Tracks with a previous attempt (spotify_enriched = True
or False) are skipped unless --retry-failed is passed.

Usage
-----
  python -m phi.meta.spotify_bulk_enrich            # enrich all unattempted
  python -m phi.meta.spotify_bulk_enrich --limit 50
  python -m phi.meta.spotify_bulk_enrich --retry-failed
  python -m phi.meta.spotify_bulk_enrich --dry-run

Returns
-------
  SpotifyBulkResult  (also printable via __str__)
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_PHI = Path.home() / ".phi"
_META_DB = _PHI / "meta.db"


# ── result ────────────────────────────────────────────────────────────────────

@dataclass
class SpotifyBulkResult:
    attempted:  int = 0
    succeeded:  int = 0
    failed:     int = 0
    skipped:    int = 0
    errors:     list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"Spotify bulk enrich: "
            f"{self.succeeded} matched / {self.attempted} attempted "
            f"({self.failed} no-match, {self.skipped} skipped)"
        )


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_annotation(conn: sqlite3.Connection, path: str) -> dict:
    row = conn.execute(
        "SELECT data FROM annotations WHERE path = ?", (path,)
    ).fetchone()
    if row is None:
        return {}
    try:
        return json.loads(row[0]) or {}
    except Exception:
        return {}


def _upsert_annotation(conn: sqlite3.Connection, path: str, updates: dict) -> None:
    existing = _get_annotation(conn, path)
    merged   = {**existing, **updates}
    payload  = json.dumps(merged, ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO annotations (path, data, updated_at)
             VALUES (?, ?, datetime('now'))
        ON CONFLICT(path) DO UPDATE
           SET data       = excluded.data,
               updated_at = excluded.updated_at
        """,
        (path, payload),
    )


# ── core runner ───────────────────────────────────────────────────────────────

def run_bulk_enrich(
    *,
    limit:         Optional[int] = None,
    retry_failed:  bool          = False,
    dry_run:       bool          = False,
    on_progress:   Optional[callable] = None,
) -> SpotifyBulkResult:
    """
    Batch-enrich all unattempted (or previously-failed) tracks.

    Parameters
    ----------
    limit           Max number of tracks to attempt (None = unlimited).
    retry_failed    If True, also retry tracks where spotify_enriched=False.
    dry_run         If True, do the lookup but don't write to the database.
    on_progress     Optional callback(done, total, path, matched) called per track.

    Returns
    -------
    SpotifyBulkResult with counts.
    """
    result = SpotifyBulkResult()

    if not _META_DB.exists():
        result.errors.append("meta.db not found — run phi at least once first")
        return result

    # Build Spotify client
    from phi.meta.spotify_client import SpotifyClient, build_spotify_client
    client = build_spotify_client()
    if client is None or not client.available:
        result.errors.append(
            "Spotify client unavailable — credentials invalid or not configured.\n"
            "  1. Go to https://developer.spotify.com/dashboard and create/rotate credentials.\n"
            "  2. Update phi_config.yaml:\n"
            "       spotify:\n"
            "         client_id:     \"YOUR_ID\"\n"
            "         client_secret: \"YOUR_SECRET\"\n"
            "  3. Run: pip install spotipy  (if not already installed)"
        )
        return result

    conn = sqlite3.connect(str(_META_DB))
    conn.row_factory = sqlite3.Row

    # Pull all tracks + their current annotations
    tracks = conn.execute(
        "SELECT path, title, artist, album FROM tracks"
    ).fetchall()

    candidates: list[dict] = []
    for t in tracks:
        ann = _get_annotation(conn, t["path"])
        sp_val = ann.get("spotify_enriched")  # None | True | False
        if sp_val is True:
            result.skipped += 1
            continue
        if sp_val is False and not retry_failed:
            result.skipped += 1
            continue
        candidates.append({
            "path":   t["path"],
            "title":  t["title"] or "",
            "artist": t["artist"] or "",
            "album":  t["album"]  or "",
            "isrc":   ann.get("isrc", ""),
        })

    if limit is not None:
        candidates = candidates[:limit]

    total = len(candidates)

    for i, cand in enumerate(candidates):
        path   = cand["path"]
        result.attempted += 1

        sp_track = None

        # Prefer ISRC exact-match
        isrc = (cand["isrc"] or "").strip()
        if isrc:
            sp_track = client.enrich_track_by_isrc(isrc)

        # Fall back to title + artist fuzzy search
        if sp_track is None and (cand["title"] or cand["artist"]):
            sp_track = client.enrich_track(
                cand["title"], cand["artist"], cand["album"]
            )

        if sp_track is not None:
            ann_update = sp_track.as_annotation_dict()
            result.succeeded += 1
        else:
            ann_update = {"spotify_enriched": False}
            result.failed += 1

        if not dry_run:
            _upsert_annotation(conn, path, ann_update)
            conn.commit()

        if on_progress:
            on_progress(i + 1, total, path, sp_track is not None)

    conn.close()
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

def _main(argv: list[str] | None = None) -> None:
    import argparse
    import os
    import sys

    parser = argparse.ArgumentParser(
        prog="python -m phi.meta.spotify_bulk_enrich",
        description="Batch-enrich all library tracks with Spotify metadata.",
    )
    parser.add_argument(
        "--limit", "-n", type=int, default=None,
        help="Max tracks to attempt (default: all unattempted)",
    )
    parser.add_argument(
        "--retry-failed", action="store_true",
        help="Also retry tracks where a previous attempt returned no match",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Look up tracks but don't write to the database",
    )
    args = parser.parse_args(argv)

    print("Starting Spotify bulk enrichment…", flush=True)
    if args.dry_run:
        print("  (dry-run — no writes)", flush=True)

    def _progress(done: int, total: int, path: str, matched: bool) -> None:
        mark = "✓" if matched else "–"
        name = os.path.basename(path)[:50]
        print(f"  [{done:>4}/{total}] {mark} {name}", flush=True)

    result = run_bulk_enrich(
        limit=args.limit,
        retry_failed=args.retry_failed,
        dry_run=args.dry_run,
        on_progress=_progress,
    )

    print()
    print(str(result))
    if result.errors:
        for e in result.errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _main()
