# -*- coding: utf-8 -*-
"""phi.models._derivative_features — feature engineering for SongDerivativeModel.

Feature groups, percentile quantization, row assembly, and social coverage
diagnostics.  Depends on _derivative_loaders for raw dict data.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from phi.models._derivative_loaders import (
    _load_state,
    _load_annotations,
    _load_store,
    _load_tags,
)


# ── Feature groups ────────────────────────────────────────────────────────────

GROUP_A: list[str] = [
    "bpm_consensus", "bpm_confidence", "bpm", "deezer_bpm",
    "loudness_rms", "dynamic_range", "deezer_gain",
    "spectral_cent", "harmonic_ratio", "zcr", "energy_heuristic",
    "key_idx", "key_confidence",
    "energy", "chroma_var",
]

GROUP_B: list[str] = [
    "year",
    "duration",
    "artist_lib_count",
    "album_lib_count",
    "spotify_popularity",
    "lfm_listeners", "lfm_playcount",
    "discogs_community_rating", "discogs_desirability", "discogs_have", "discogs_want",
    "deezer_rank",
    "meta_score",
]

_ALL_FEATURE_COLS = GROUP_A + GROUP_B


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_float(v: Any) -> float:
    if v is None:
        return float("nan")
    try:
        f = float(v)
        return f if math.isfinite(f) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def _compute_lib_counts(tags: dict[str, dict]) -> dict[str, dict]:
    """
    Compute artist_lib_count / album_lib_count per track.

    An artist with 20 tracks in the library is presumably more valued
    than one with 1 track — a collector-intensity proxy.
    """
    from collections import Counter
    artist_counts: Counter = Counter()
    album_counts:  Counter = Counter()
    for info in tags.values():
        a = (info.get("artist") or "").strip().lower()
        b = (info.get("album")  or "").strip().lower()
        if a:
            artist_counts[a] += 1
        if b:
            album_counts[b] += 1

    result: dict[str, dict] = {}
    for path, info in tags.items():
        a = (info.get("artist") or "").strip().lower()
        b = (info.get("album")  or "").strip().lower()
        result[path] = {
            "artist_lib_count": float(artist_counts.get(a, 1)),
            "album_lib_count":  float(album_counts.get(b, 1)),
        }
    return result


def _synthetic_target(srec: dict, ann: dict, lib: dict) -> float:
    """
    Fallback quality proxy for tracks with no play stats or meta_score.

    Combines harmonic_ratio (35%), loudness_rms (25%), bpm_confidence (15%),
    artist_lib_count (25%).  All sub-scores clamped to [0, 1].
    """
    import math as _m

    def _c(v: float) -> float:
        return max(0.0, min(1.0, v)) if not _m.isnan(v) else _m.nan

    hr  = _c(_to_float(ann.get("harmonic_ratio")  or srec.get("harmonic_ratio")))
    rms = _c(_to_float(srec.get("loudness_rms")) * 5.0)
    bc  = _c(_to_float(ann.get("bpm_confidence") or srec.get("bpm_confidence")))
    cnt = _to_float(lib.get("artist_lib_count", 1.0))
    alc = _c(_m.log(max(1.0, cnt)) / _m.log(100.0))

    weights  = [(hr, 0.35), (rms, 0.25), (bc, 0.15), (alc, 0.25)]
    num, den = 0.0, 0.0
    for v, w in weights:
        if not _m.isnan(v):
            num += v * w
            den += w
    return (num / den) if den > 0 else 0.5


def _percentile_rank(X: np.ndarray) -> np.ndarray:
    """
    Replace each column with its percentile rank among non-NaN values in [1/n, 1].
    NaN values stay NaN.

    Quantizes all features to the same relative scale so that "high BPM"
    and "high popularity" are directly comparable.
    """
    from scipy.stats import rankdata
    out = np.full_like(X, np.nan, dtype=np.float64)
    for j in range(X.shape[1]):
        col  = X[:, j]
        mask = ~np.isnan(col)
        n    = mask.sum()
        if n < 2:
            out[mask, j] = 0.5
            continue
        ranks = rankdata(col[mask], method="average")
        out[mask, j] = ranks / n
    return out


def _assemble_rows(paths: list[str]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """
    Assemble the feature matrix and target vector for *paths*.

    Feature resolution order (per column):
      1. annotations table   — enricher output
      2. meta_store.jsonl    — librosa features
      3. tracks table        — tag fields (year, duration, artist, album)
      4. lib_counts          — computed artist_lib_count / album_lib_count

    Target resolution order:
      1. play_stats.elo_score
      2. play_stats.engagement_score
      3. annotations.meta_score
      4. _synthetic_target()

    Returns
    -------
    X_q   : float32 (n, n_features) — percentile-ranked features
    y     : float64 (n,)            — target (always finite after synthesis)
    valid : list[str]               — path order matching X_q rows
    """
    state        = _load_state()
    play_stats   = state.get("play_stats", {})
    annotations  = _load_annotations()
    store        = _load_store()
    tags         = _load_tags()
    lib_counts   = _compute_lib_counts(tags)

    raw_rows: list[list[float]] = []
    targets:  list[float]       = []
    valid:    list[str]         = []

    for path in paths:
        ann  = annotations.get(path, {})
        srec = store.get(path, {})
        tag  = tags.get(path, {})
        lib  = lib_counts.get(path, {})
        stat = play_stats.get(path, {})

        row: list[float] = []
        for feat in _ALL_FEATURE_COLS:
            v = ann.get(feat)
            if v is None:
                v = srec.get(feat)
            if v is None:
                raw = tag.get(feat)
                if raw is not None:
                    v = str(raw)[:4] if feat == "year" and raw else raw
            if v is None:
                v = lib.get(feat)
            row.append(_to_float(v))
        raw_rows.append(row)

        t = _to_float(stat.get("elo_score"))
        if math.isnan(t):
            t = _to_float(stat.get("engagement_score"))
        if math.isnan(t):
            t = _to_float(ann.get("meta_score"))
        if math.isnan(t):
            t = _synthetic_target(srec, ann, lib)
        targets.append(t)
        valid.append(path)

    if not raw_rows:
        return (
            np.empty((0, len(_ALL_FEATURE_COLS)), dtype=np.float32),
            np.empty(0, dtype=np.float64),
            [],
        )

    X_raw = np.array(raw_rows, dtype=np.float64)
    X_q   = _percentile_rank(X_raw).astype(np.float32)
    y     = np.array(targets, dtype=np.float64)

    return X_q, y, valid


def social_coverage(paths: list[str] | None = None) -> dict:
    """
    Diagnostic: report per-field coverage for GROUP_B social features.

    Returns a dict with 'n_tracks' and 'coverage' (field → fraction non-NaN).
    """
    state = _load_state()
    if paths is None:
        from pathlib import Path as _Path
        paths = [p for p in state.get("playlist", []) if _Path(p).exists()]
    if not paths:
        return {"n_tracks": 0, "coverage": {}}

    annotations = _load_annotations()
    store       = _load_store()
    tags        = _load_tags()
    lib_counts  = _compute_lib_counts(tags)

    counts = {f: 0 for f in GROUP_B}
    for path in paths:
        ann  = annotations.get(path, {})
        srec = store.get(path, {})
        tag  = tags.get(path, {})
        lib  = lib_counts.get(path, {})
        for feat in GROUP_B:
            v = ann.get(feat) or srec.get(feat) or tag.get(feat) or lib.get(feat)
            if v is not None and _to_float(v) == _to_float(v):
                counts[feat] += 1

    n = len(paths)
    return {
        "n_tracks":  n,
        "coverage":  {f: round(counts[f] / n, 3) for f in GROUP_B},
    }
