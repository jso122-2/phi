# -*- coding: utf-8 -*-
"""phi.meta.dataset_export — turn meta_store into ML-ready training data.

Reads ~/.phi/meta_store.jsonl (built by batch_extractor) and exports:

  ~/.phi/dataset/
    dataset.jsonl       — one enriched record per track (all fields)
    features.npy        — float32 matrix  (N × D)
    feature_names.json  — column names for features.npy
    labels.json         — discrete bucket assignments per track
    splits.json         — train / val / test path lists (80/10/10, artist-stratified)
    stats.json          — dataset statistics and bucket distributions

Bucket definitions
------------------
mood        calm / chill / focused / energetic / happy / sad / angry
            Priority: Spotify valence+energy > heuristic BPM+RMS
energy_lvl  0 (quiet) – 4 (intense), quantized from spotify_energy or RMS
tempo_cls   slow (<80) / medium (80–120) / uptempo (120–150) / fast (>150)
key_mode    major / minor / unknown
            Priority: Spotify mode field > chroma-based estimate

Annotation merge
----------------
Before building features, annotations are bulk-fetched from ~/.phi/meta.db
(the same SQLite written by EnrichDaemon) and merged into each meta_store
record.  This means Spotify audio features (spotify_valence, spotify_energy,
etc.), Last.fm tags (lfm_tags), and MusicBrainz genres (mb_genres) are all
available to feature builders and bucket helpers.

Usage
-----
    python -m phi.meta.dataset_export
    python -m phi.meta.dataset_export --min-tracks 500 --out ~/my_dataset
"""
from __future__ import annotations

import json
import os
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent.parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

META_STORE  = Path.home() / ".phi" / "meta_store.jsonl"
STATE_FILE  = Path.home() / ".phi" / "state.json"
DATASET_DIR = Path.home() / ".phi" / "dataset"
META_DB     = Path.home() / ".phi" / "meta.db"


# ---------------------------------------------------------------------------
# Annotation store reader
# ---------------------------------------------------------------------------

def _load_annotations(paths: list[str], db_path: Path = META_DB) -> dict[str, dict]:
    """
    Bulk-fetch all annotation rows from the EnrichDaemon's SQLite store for
    the given paths.  Returns {path: annotation_dict}.  Silently returns an
    empty dict if the DB doesn't exist or the table is missing.
    """
    if not db_path.exists():
        return {}

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        placeholders = ",".join("?" * len(paths))
        rows = conn.execute(
            f"SELECT path, data FROM annotations WHERE path IN ({placeholders})",
            paths,
        ).fetchall()
        conn.close()
    except Exception:
        return {}

    result: dict[str, dict] = {}
    for row in rows:
        try:
            result[row["path"]] = json.loads(row["data"])
        except Exception:
            pass
    return result

# ---------------------------------------------------------------------------
# Bucketing helpers
# ---------------------------------------------------------------------------

def _mood_bucket(rec: dict) -> str:
    """Derive mood label.  Spotify features take priority over heuristics."""
    # Tier 1: Spotify valence + energy (stored with spotify_ prefix by EnrichDaemon)
    v = rec.get("spotify_valence")
    e = rec.get("spotify_energy")
    if v is not None and e is not None:
        if v >= 0.65 and e >= 0.60:
            return "energetic"
        if v >= 0.65:
            return "happy"
        if v < 0.25 and e >= 0.60:
            return "angry"
        if v < 0.25:
            return "sad"
        if e < 0.30:
            return "calm"
        if e < 0.50:
            return "chill"
        return "focused"

    # Tier 2: heuristic from batch_extractor
    h = rec.get("mood_heuristic")
    if h:
        return h

    # Tier 3: BPM only
    bpm = rec.get("bpm") or 0
    if bpm < 75:
        return "calm"
    if bpm < 100:
        return "chill"
    if bpm < 130:
        return "focused"
    return "energetic"


def _energy_level(rec: dict) -> int:
    """0–4 energy bucket.  Prefers Spotify energy over local RMS heuristic."""
    e = rec.get("spotify_energy") or rec.get("energy_heuristic") or 0.0
    if e < 0.2:
        return 0
    if e < 0.4:
        return 1
    if e < 0.6:
        return 2
    if e < 0.8:
        return 3
    return 4


def _tempo_class(rec: dict) -> str:
    """Prefers Spotify tempo over librosa BPM estimate."""
    bpm = rec.get("spotify_tempo") or rec.get("bpm") or 0.0
    if bpm < 80:
        return "slow"
    if bpm < 120:
        return "medium"
    if bpm < 150:
        return "uptempo"
    return "fast"


def _key_mode(rec: dict) -> str:
    """Prefers Spotify mode (0=minor, 1=major) over chroma estimate."""
    mode = rec.get("spotify_mode")
    if mode == 1:
        return "major"
    if mode == 0:
        return "minor"
    return "unknown"


def _genre_label(rec: dict) -> str:
    """Best available genre string."""
    for field in ("lfm_tags", "mb_genres", "genre"):
        val = rec.get(field)
        if isinstance(val, list) and val:
            return val[0].lower().strip()
        if isinstance(val, str) and val:
            return val.lower().strip()
    return "unknown"


# ---------------------------------------------------------------------------
# Feature vector builder
# ---------------------------------------------------------------------------

FEATURE_NAMES: list[str] = [
    # ── Spotify continuous features (0.0 if track not Spotify-enriched) ───────
    "spotify_valence",
    "spotify_energy",
    "spotify_danceability",
    "spotify_acousticness",
    "spotify_instrumentalness",
    "spotify_liveness",
    "spotify_speechiness",
    "spotify_tempo_norm",        # spotify_tempo / 250
    "spotify_loudness_norm",     # (spotify_loudness + 60) / 60

    # ── Local librosa rhythm features ─────────────────────────────────────────
    "bpm_norm",                  # bpm / 250
    "onset_mean",
    "onset_std",

    # ── Local librosa tonal features ──────────────────────────────────────────
    "chroma_var",
    *[f"tonnetz_{i}" for i in range(6)],   # 6D tonal centroid

    # ── Local librosa timbre features ─────────────────────────────────────────
    "loudness_rms",
    "dynamic_range_norm",        # dynamic_range / 60
    "spectral_cent_norm",        # centroid / 8000
    "spectral_rolloff_norm",     # rolloff / 8000
    "spectral_bw_norm",          # bandwidth / 4000
    *[f"spectral_contrast_{i}" for i in range(7)],   # 7-band contrast
    "harmonic_ratio",
    "zcr",
    *[f"mfcc_{i}" for i in range(1, 14)],  # MFCC 1–13

    # ── Deezer features (0.0 if not enriched) ─────────────────────────────────
    "deezer_bpm_norm",           # deezer_bpm / 250
    "deezer_gain_norm",          # (deezer_gain + 12) / 24  (gain typically -12..+12 dB)
    "deezer_explicit",           # 0.0 or 1.0
    "deezer_rank_norm",          # deezer_rank / 1_000_000

    # ── Discogs community features (0.0 if not enriched) ─────────────────────
    "discogs_community_rating_norm",  # rating / 5
    "discogs_desirability",           # want / (have + want + 1)

    # ── Source presence flags (float) ─────────────────────────────────────────
    "has_spotify",
    "has_lfm",
    "has_deezer",
    "has_discogs",

    # ── Playback stats (0.0 if never played) ──────────────────────────────────
    "plays_norm",                # plays / 100
    "elo_norm",                  # (elo_score - 1500) / 500
    "completion_rate",
    "skip_rate_norm",            # skip_count / max(plays, 1) clamped 0–1
    "duration_norm",             # duration / 600
]


def _feature_vector(rec: dict) -> list[float]:
    def _f(key: str, default: float = 0.0) -> float:
        v = rec.get(key)
        return float(v) if v is not None else default

    def _pad(lst, n: int) -> list[float]:
        """Pad or truncate a list to exactly n floats."""
        out = [float(v) for v in (lst or [])]
        return (out + [0.0] * n)[:n]

    mfcc     = _pad(rec.get("mfcc_mean"),        13)
    tonnetz  = _pad(rec.get("tonnetz_mean"),       6)
    contrast = _pad(rec.get("spectral_contrast"),  7)

    sp_loud = rec.get("spotify_loudness") or -60.0
    plays   = _f("plays")

    return [
        # Spotify
        _f("spotify_valence"),
        _f("spotify_energy"),
        _f("spotify_danceability"),
        _f("spotify_acousticness"),
        _f("spotify_instrumentalness"),
        _f("spotify_liveness"),
        _f("spotify_speechiness"),
        min(1.0, _f("spotify_tempo") / 250),
        max(0.0, min(1.0, (sp_loud + 60) / 60)),

        # Rhythm
        min(1.0, _f("bpm") / 250),
        _f("onset_mean"),
        _f("onset_std"),

        # Tonal
        _f("chroma_var"),
        *tonnetz,

        # Timbre
        _f("loudness_rms"),
        min(1.0, max(0.0, _f("dynamic_range") / 60)),
        min(1.0, _f("spectral_cent") / 8000),
        min(1.0, _f("spectral_rolloff") / 8000),
        min(1.0, _f("spectral_bw") / 4000),
        *contrast,
        _f("harmonic_ratio"),
        _f("zcr"),
        *mfcc,

        # Deezer
        min(1.0, _f("deezer_bpm") / 250),
        max(0.0, min(1.0, (_f("deezer_gain") + 12) / 24)),
        1.0 if rec.get("deezer_explicit") else 0.0,
        min(1.0, _f("deezer_rank") / 1_000_000),

        # Discogs community
        min(1.0, _f("discogs_community_rating") / 5),
        _f("discogs_desirability"),

        # Source presence flags
        1.0 if rec.get("spotify_enriched") else 0.0,
        1.0 if rec.get("lfm_enriched")     else 0.0,
        1.0 if rec.get("deezer_enriched")  else 0.0,
        1.0 if rec.get("discogs_enriched") else 0.0,

        # Playback stats
        min(1.0, plays / 100),
        max(-1.0, min(1.0, (_f("elo_score", 1500) - 1500) / 500)),
        _f("completion_rate"),
        min(1.0, _f("skip_count") / max(plays, 1)),
        min(1.0, _f("duration") / 600),
    ]


# ---------------------------------------------------------------------------
# Artist-stratified train/val/test split
# ---------------------------------------------------------------------------

def _split(paths: list[str], records: dict[str, dict], seed: int = 42) -> dict:
    """
    80 / 10 / 10 split, grouped by artist so an artist's tracks don't
    span train and test (prevents data leakage in similarity models).
    """
    rng = random.Random(seed)

    by_artist: dict[str, list[str]] = defaultdict(list)
    for p in paths:
        artist = records.get(p, {}).get("artist") or "unknown"
        by_artist[artist].append(p)

    artists = list(by_artist.keys())
    rng.shuffle(artists)

    n   = len(artists)
    n_val  = max(1, n // 10)
    n_test = max(1, n // 10)

    val_artists  = set(artists[:n_val])
    test_artists = set(artists[n_val:n_val + n_test])
    train_artists = set(artists[n_val + n_test:])

    split_result: dict[str, list[str]] = {"train": [], "val": [], "test": []}
    for artist, apaths in by_artist.items():
        if artist in val_artists:
            split_result["val"].extend(apaths)
        elif artist in test_artists:
            split_result["test"].extend(apaths)
        else:
            split_result["train"].extend(apaths)

    return split_result


# ---------------------------------------------------------------------------
# Main export
# ---------------------------------------------------------------------------

def export(
    store_path: Path = META_STORE,
    out_dir: Path = DATASET_DIR,
    *,
    min_tracks: int = 0,
    db_path: Path = META_DB,
    verbose: bool = True,
) -> Path:
    """
    Build the training dataset from *store_path* and write to *out_dir*.
    Returns *out_dir*.

    Parameters
    ----------
    store_path  Local feature store written by batch_extractor (meta_store.jsonl).
    out_dir     Destination directory for exported dataset files.
    min_tracks  Warn (but don't abort) if fewer valid tracks are found.
    db_path     SQLite DB written by EnrichDaemon (default: ~/.phi/meta.db).
                Annotations (Spotify, Last.fm, MusicBrainz) are merged in from here.
    verbose     Print progress to stdout.
    """
    if not store_path.exists():
        raise FileNotFoundError(f"meta_store not found: {store_path}. "
                                "Run `python -m phi.meta.batch_extractor` first.")

    # Load records
    records: dict[str, dict] = {}
    with store_path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    r = json.loads(line)
                    records[r["path"]] = r
                except Exception:
                    pass

    # Merge enrichment annotations (Spotify, Last.fm, MusicBrainz) from meta.db.
    # These are written by EnrichDaemon and not present in meta_store.jsonl.
    annotations = _load_annotations(list(records.keys()), db_path)
    ann_count = 0
    for path, ann in annotations.items():
        if path in records:
            records[path].update(ann)
            ann_count += 1
    if verbose and annotations:
        sp_count  = sum(1 for a in annotations.values() if a.get("spotify_enriched"))
        lfm_count = sum(1 for a in annotations.values() if a.get("lfm_enriched"))
        mb_count  = sum(1 for a in annotations.values() if a.get("mb_enriched"))
        print(f"Annotations merged  : {ann_count} tracks  "
              f"(Spotify: {sp_count}, Last.fm: {lfm_count}, MusicBrainz: {mb_count})")

    # Also cross-reference play_stats from state.json
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
            play_stats = state.get("play_stats", {})
            for path, stats in play_stats.items():
                if path in records:
                    records[path].update({
                        "plays":           stats.get("plays", 0),
                        "elo_score":       stats.get("elo_score", 1500),
                        "skip_count":      stats.get("skip_count", 0),
                        "completion_rate": stats.get("completion_rate", 0.0),
                        "played_seconds":  stats.get("played_seconds", 0.0),
                    })
        except Exception:
            pass

    # Filter to records with at least BPM extracted
    valid = {p: r for p, r in records.items()
             if "bpm" in r and not r.get("error")}

    if verbose:
        print(f"Records in store : {len(records)}")
        print(f"Valid (have BPM) : {len(valid)}")
        if len(valid) < min_tracks:
            print(f"WARNING: only {len(valid)} valid tracks (min_tracks={min_tracks})")

    paths = list(valid.keys())

    # ── add bucket labels to each record ─────────────────────────────────────
    for path, rec in valid.items():
        rec["_mood"]       = _mood_bucket(rec)
        rec["_energy_lvl"] = _energy_level(rec)
        rec["_tempo_cls"]  = _tempo_class(rec)
        rec["_key_mode"]   = _key_mode(rec)
        rec["_genre"]      = _genre_label(rec)

    # ── feature matrix ────────────────────────────────────────────────────────
    try:
        import numpy as np
        feat_matrix = np.array([_feature_vector(valid[p]) for p in paths],
                               dtype=np.float32)
        # Standardise each column
        col_mean = feat_matrix.mean(axis=0)
        col_std  = feat_matrix.std(axis=0)
        col_std[col_std == 0] = 1.0
        feat_norm = (feat_matrix - col_mean) / col_std
        has_numpy = True
    except ImportError:
        has_numpy = False
        if verbose:
            print("numpy not available — skipping features.npy")

    # ── splits ────────────────────────────────────────────────────────────────
    splits = _split(paths, valid)

    # ── statistics ───────────────────────────────────────────────────────────
    mood_dist   = Counter(r["_mood"]       for r in valid.values())
    energy_dist = Counter(r["_energy_lvl"] for r in valid.values())
    tempo_dist  = Counter(r["_tempo_cls"]  for r in valid.values())
    genre_dist  = Counter(r["_genre"]      for r in valid.values())
    def _pct(key: str) -> float:
        return sum(1 for r in valid.values() if r.get(key)) / max(len(valid), 1) * 100

    stats = {
        "total_tracks": len(valid),
        "train":        len(splits["train"]),
        "val":          len(splits["val"]),
        "test":         len(splits["test"]),
        "enrichment_coverage": {
            "spotify_pct":  round(_pct("spotify_enriched"),  1),
            "lfm_pct":      round(_pct("lfm_enriched"),      1),
            "mb_pct":       round(_pct("mb_enriched"),       1),
            "discogs_pct":  round(_pct("discogs_enriched"),  1),
            "deezer_pct":   round(_pct("deezer_enriched"),   1),
        },
        "mood_distribution":    dict(mood_dist.most_common()),
        "energy_distribution":  dict(sorted(energy_dist.items())),
        "tempo_distribution":   dict(tempo_dist.most_common()),
        "top_genres":           dict(genre_dist.most_common(20)),
        "feature_dim":          len(FEATURE_NAMES),
        "feature_names":        FEATURE_NAMES,
    }

    # ── write outputs ─────────────────────────────────────────────────────────
    out_dir.mkdir(parents=True, exist_ok=True)

    # dataset.jsonl
    ds_path = out_dir / "dataset.jsonl"
    with ds_path.open("w") as fh:
        for p in paths:
            fh.write(json.dumps(valid[p], ensure_ascii=False) + "\n")

    # features.npy + feature_names.json
    if has_numpy:
        import numpy as np
        np.save(out_dir / "features.npy", feat_norm)
        np.save(out_dir / "features_raw.npy", feat_matrix)
        (out_dir / "feature_names.json").write_text(
            json.dumps({"names": FEATURE_NAMES, "mean": col_mean.tolist(),
                        "std": col_std.tolist()}, indent=2)
        )

    # labels.json — path → bucket dict
    labels = {p: {"mood": r["_mood"], "energy_lvl": r["_energy_lvl"],
                  "tempo_cls": r["_tempo_cls"], "key_mode": r["_key_mode"],
                  "genre": r["_genre"]}
              for p, r in valid.items()}
    (out_dir / "labels.json").write_text(json.dumps(labels, indent=2))

    # splits.json
    (out_dir / "splits.json").write_text(json.dumps(splits, indent=2))

    # stats.json
    (out_dir / "stats.json").write_text(json.dumps(stats, indent=2))

    if verbose:
        print(f"\n── Dataset written to {out_dir} ──")
        print(f"  dataset.jsonl : {len(valid)} records")
        if has_numpy:
            print(f"  features.npy  : {feat_norm.shape}  (standardised)")
        print(f"  splits        : {len(splits['train'])} train / "
              f"{len(splits['val'])} val / {len(splits['test'])} test")
        print(f"\n── Mood distribution ──")
        for mood, cnt in mood_dist.most_common():
            bar = "█" * (cnt * 30 // max(mood_dist.values()))
            print(f"  {mood:<12} {cnt:>4}  {bar}")
        print(f"\n── Tempo classes ──")
        for cls, cnt in tempo_dist.most_common():
            print(f"  {cls:<10} {cnt:>4}")
        cov = stats["enrichment_coverage"]
        print(f"\n── Enrichment coverage ──")
        print(f"  MusicBrainz : {cov['mb_pct']:.0f}%")
        print(f"  Spotify     : {cov['spotify_pct']:.0f}%")
        print(f"  Last.fm     : {cov['lfm_pct']:.0f}%")
        print(f"  Deezer      : {cov['deezer_pct']:.0f}%")
        print(f"  Discogs     : {cov['discogs_pct']:.0f}%")
        print(f"\n  Top genres: {', '.join(g for g, _ in genre_dist.most_common(5))}")

    return out_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m phi.meta.dataset_export",
        description="Export phi metadata store as an ML training dataset.",
    )
    parser.add_argument("--store", type=Path, default=META_STORE,
                        help=f"Input JSONL store (default: {META_STORE})")
    parser.add_argument("--out",   type=Path, default=DATASET_DIR,
                        help=f"Output directory (default: {DATASET_DIR})")
    parser.add_argument("--db",    type=Path, default=META_DB,
                        help=f"SQLite annotation DB written by EnrichDaemon (default: {META_DB})")
    parser.add_argument("--min-tracks", type=int, default=0,
                        help="Warn if fewer than this many valid tracks")
    args = parser.parse_args(argv)

    export(store_path=args.store, out_dir=args.out, min_tracks=args.min_tracks,
           db_path=args.db)


if __name__ == "__main__":
    main()
