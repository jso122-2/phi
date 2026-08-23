# -*- coding: utf-8 -*-
"""phi.meta._track_helpers — low-level data loaders, telemetry builder, and JSON helpers.

All functions are stateless and dependency-free (only stdlib + optional numpy).
Paths are passed in; no module-level path state.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Feature/annotation partition constants ────────────────────────────────────

_ANNOTATION_PREFIXES: tuple[str, ...] = (
    "spotify_", "lfm_", "mb_", "discogs_", "deezer_",
    "acoustid_", "librosa_",
    "bpm_consensus", "genre_consensus", "meta_score", "meta_fields_",
    "lyrics_", "lyrics_text",
    "mb_artist_", "artist_mbid",
)

_LIBROSA_FIELDS: set[str] = {
    "bpm", "onset_mean", "onset_std",
    "key", "key_idx", "chroma_var", "tonnetz_mean",
    "loudness_rms", "dynamic_range",
    "spectral_cent", "spectral_rolloff", "spectral_bw", "spectral_contrast",
    "harmonic_ratio", "zcr", "mfcc_mean",
    "energy_heuristic", "mood_heuristic",
    "extracted_at", "librosa_error",
}

_META_FIELDS: set[str] = {
    "title", "artist", "album", "album_artist",
    "track_num", "track", "disc_num", "year", "genre",
    "duration", "bpm", "key_sig", "comment",
}

_SECS_PER_DAY = 86_400.0


# ── Feature partition helpers ─────────────────────────────────────────────────

def _is_annotation(key: str) -> bool:
    """Return True when *key* belongs to an enrichment annotation namespace."""
    return any(key.startswith(p) or key == p for p in _ANNOTATION_PREFIXES)


def _split_features(store_rec: dict) -> dict:
    """Return only the librosa/audio feature keys from a meta_store record."""
    return {k: v for k, v in store_rec.items()
            if k in _LIBROSA_FIELDS and k != "path"}


# ── Data loaders ──────────────────────────────────────────────────────────────

def _load_state(state_file: Path) -> dict:
    """Read JSON state file; return {} on missing or corrupt file."""
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text())
    except Exception:
        return {}


def _load_meta_store(meta_store: Path) -> dict[str, dict]:
    """Load meta_store.jsonl → {path: record}."""
    records: dict[str, dict] = {}
    if not meta_store.exists():
        return records
    with meta_store.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rec = json.loads(line)
                    if "path" in rec:
                        records[rec["path"]] = rec
                except Exception:
                    pass
    return records


def _load_annotations_db(meta_db: Path) -> dict[str, dict]:
    """Read all annotations from meta.db → {path: annotation_dict}."""
    result: dict[str, dict] = {}
    if not meta_db.exists():
        return result
    try:
        conn = sqlite3.connect(str(meta_db))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT path, data FROM annotations").fetchall()
        for row in rows:
            try:
                result[row["path"]] = json.loads(row["data"])
            except Exception:
                pass
        conn.close()
    except Exception:
        pass
    return result


def _load_tag_db(meta_db: Path) -> dict[str, dict]:
    """Read file tags from meta.db tracks table → {path: tag_dict}."""
    result: dict[str, dict] = {}
    if not meta_db.exists():
        return result
    try:
        conn = sqlite3.connect(str(meta_db))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT path, title, artist, album, album_artist, track_num, "
            "disc_num, year, genre, duration, bpm, key_sig, comment, art_bytes "
            "FROM tracks"
        ).fetchall()
        for row in rows:
            result[row["path"]] = {
                "title":        row["title"],
                "artist":       row["artist"],
                "album":        row["album"],
                "album_artist": row["album_artist"],
                "track_num":    row["track_num"],
                "disc_num":     row["disc_num"],
                "year":         row["year"],
                "genre":        row["genre"],
                "duration":     row["duration"],
                "bpm":          row["bpm"],
                "key_sig":      row["key_sig"],
                "comment":      row["comment"],
                "art_bytes":    row["art_bytes"],
            }
        conn.close()
    except Exception:
        pass
    return result


# ── Telemetry heuristics ──────────────────────────────────────────────────────

def _build_telemetry(path: str, play_stats: dict, duration: float) -> dict:
    """Merge raw play_stats with derived engagement heuristics.

    Returns dict with fields: added, elo_score, skip_count, played_seconds,
    completion_rate, listen_days_since_added, estimated_plays,
    skip_rate_heuristic, engagement_score, listen_intensity, telemetry_written_at.
    """
    out: dict[str, Any] = dict(play_stats)

    added_str = play_stats.get("added")
    if added_str:
        try:
            added_dt = datetime.fromisoformat(added_str)
            if added_dt.tzinfo is None:
                added_dt = added_dt.replace(tzinfo=timezone.utc)
            delta = (datetime.now(timezone.utc) - added_dt).total_seconds()
            out["listen_days_since_added"] = round(delta / _SECS_PER_DAY, 2)
        except Exception:
            out["listen_days_since_added"] = None
    else:
        out["listen_days_since_added"] = None

    played_secs   = float(play_stats.get("played_seconds", 0.0))
    completion_rt = float(play_stats.get("completion_rate", 0.0))
    skip_count    = int(play_stats.get("skip_count", 0))

    if duration and duration > 0 and completion_rt > 0:
        avg_per_play    = completion_rt * duration
        estimated_plays = played_secs / max(avg_per_play, 1.0)
    else:
        estimated_plays = 0.0
    out["estimated_plays"] = round(estimated_plays, 1)

    total_starts = estimated_plays + skip_count
    skip_rate    = skip_count / max(total_starts, 1.0)
    out["skip_rate_heuristic"] = round(skip_rate, 4)
    out["engagement_score"]    = round(completion_rt * (1.0 - skip_rate), 4)

    days = out.get("listen_days_since_added") or 0.0
    if days > 0 and estimated_plays > 0:
        out["listen_intensity"] = round(estimated_plays / days, 4)
    else:
        out["listen_intensity"] = 0.0

    out["telemetry_written_at"] = datetime.now(timezone.utc).isoformat()
    return out


# ── JSON helpers ──────────────────────────────────────────────────────────────

def _json_default(obj: Any) -> Any:
    """JSON encoder for numpy scalars and arrays. Raises TypeError for unknown types."""
    try:
        import numpy as np
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
    except ImportError:
        pass
    raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")


def _write_json(path: Path, data: dict) -> None:
    """Write *data* to *path* as indented JSON, handling numpy types."""
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False,
                               default=_json_default))
