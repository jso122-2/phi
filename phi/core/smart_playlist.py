# -*- coding: utf-8 -*-
"""phi.core.smart_playlist — rule-based and arc-shaped playlist generator.

DSL syntax (rules are space-separated; all are ANDed together):

    bpm:120-130          BPM in range [120, 130]
    bpm:>=120            BPM >= 120
    bpm:<=130            BPM <= 130
    rating:>=3           star rating >= 3
    rating:5             exactly 5 stars
    plays:>=10           played 10+ times
    plays:0              never played
    never-heard          alias for plays:0
    artist:reznor        artist field contains "reznor" (case-insensitive)
    album:social         album field contains "social"
    genre:electronic     genre field contains "electronic"
    mood:dark            mood annotation == "dark"
    key:c#               key annotation contains "c#"
    added:7d             added to library within the last 7 days
    added:last-week      same as added:7d
    added:last-month     added:30d
    duration:120-300     duration between 2 and 5 minutes (seconds)
    duration:<=180       duration ≤ 3 minutes
    energy:calm          mood bucket (calm / chill / focused / energetic)

    --- ranking / listening depth (from play_stats) ---
    completion_rate:>=0.7   tracks you finish more than 70% of the time
    completion_rate:<=0.3   tracks you typically skip
    skip_count:<=2          skipped at most twice ever
    skip_count:0            never skipped
    played_mins:>=10        cumulative listening time ≥ 10 minutes
    played_secs:>=600       same in seconds
    elo:>=1600              high-ranked by the pairwise picker
    elo:<=1400              low-ranked tracks

sort=plays               sort by play count (default)
sort=rating              sort by star rating
sort=added               sort by add date (newest first)
sort=random              shuffle
sort=title               sort by display name
sort=elo                 sort by ELO score (highest first)
sort=completion          sort by completion rate (highest first)
sort=listened            sort by total minutes listened (highest first)

limit=50                 maximum tracks (default 100)

Examples:
    "bpm:>=120 bpm:<=135 rating:>=3 sort=plays limit=20"
    "completion_rate:>=0.7 mood:energetic sort=elo limit=30"
    "elo:>=1600 skip_count:0 sort=completion"
    "played_mins:>=5 never-heard sort=random limit=10"
"""
from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable


# ── types ─────────────────────────────────────────────────────────────────────

Predicate = Callable[[str, dict, dict, dict], bool]   # path, meta, ann, stats


# ── rule parser ───────────────────────────────────────────────────────────────

def _num_predicate(value: object, op: str, threshold: float) -> bool:
    """Apply comparison operator *op* between *value* and *threshold*."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    if op == ">=":  return v >= threshold
    if op == "<=":  return v <= threshold
    if op == "==":  return abs(v - threshold) < 0.5
    if op == ">":   return v > threshold
    if op == "<":   return v < threshold
    return False


def _parse_num_expr(expr: str) -> Callable[[object], bool]:
    """
    Parse an expression like ">=120", "120-130", "5", "<=130" into a
    predicate that accepts a value and returns bool.
    """
    range_m = re.fullmatch(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)", expr)
    if range_m:
        lo, hi = float(range_m.group(1)), float(range_m.group(2))
        return lambda v: _num_predicate(v, ">=", lo) and _num_predicate(v, "<=", hi)

    op_m = re.fullmatch(r"(>=|<=|>|<)(\d+(?:\.\d+)?)", expr)
    if op_m:
        op, num = op_m.group(1), float(op_m.group(2))
        return lambda v, _op=op, _n=num: _num_predicate(v, _op, _n)

    try:
        n = float(expr)
        return lambda v: _num_predicate(v, "==", n)
    except ValueError:
        return lambda v: False


def _parse_date_expr(expr: str) -> Callable[[str], bool]:
    """
    Parse an expression like "7d", "last-week", "last-month" into a predicate
    on ISO-8601 date strings.
    """
    lx = expr.lower()
    if lx in ("last-week",):
        days = 7
    elif lx in ("last-month",):
        days = 30
    else:
        m = re.fullmatch(r"(\d+)d", lx)
        if m:
            days = int(m.group(1))
        else:
            return lambda _: False

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    return lambda date_str: bool(date_str) and date_str >= cutoff


def parse_rules(rules_str: str, _library=None) -> list[Predicate]:
    """
    Parse *rules_str* into a list of predicates.
    Each predicate is: fn(path, meta, ann, stats) → bool.
    """
    predicates: list[Predicate] = []

    for token in rules_str.split():
        token_lower = token.lower()

        # ── special tokens ────────────────────────────────────────────────────
        if token_lower == "never-heard":
            predicates.append(lambda p, m, a, s: s.get("plays", 0) == 0)
            continue
        if "=" in token and not token.startswith((
            "bpm:", "rating:", "plays:", "duration:", "added:",
            "artist:", "album:", "genre:", "mood:", "key:", "energy:",
            "completion_rate:", "completion:", "skip_count:", "skips:",
            "played_mins:", "played_secs:", "elo:",
        )):
            continue   # sort=, limit= — consumed by SmartPlaylist.evaluate()

        if ":" not in token:
            continue

        key, expr = token.split(":", 1)
        key_lower  = key.lower()

        # ── numeric rules ─────────────────────────────────────────────────────
        if key_lower == "bpm":
            num_pred = _parse_num_expr(expr)
            def _bpm_rule(p, m, a, s, np=num_pred):
                v = a.get("bpm") or m.get("bpm")
                return np(v)
            predicates.append(_bpm_rule)

        elif key_lower == "rating":
            num_pred = _parse_num_expr(expr)
            def _rating_rule(p, m, a, s, np=num_pred):
                return np(s.get("rating", 0))
            predicates.append(_rating_rule)

        elif key_lower == "plays":
            num_pred = _parse_num_expr(expr)
            def _plays_rule(p, m, a, s, np=num_pred):
                return np(s.get("plays", 0))
            predicates.append(_plays_rule)

        elif key_lower == "duration":
            num_pred = _parse_num_expr(expr)
            def _dur_rule(p, m, a, s, np=num_pred):
                return np(m.get("duration", 0))
            predicates.append(_dur_rule)

        # ── date rules ────────────────────────────────────────────────────────
        elif key_lower == "added":
            date_pred = _parse_date_expr(expr)
            def _added_rule(p, m, a, s, dp=date_pred):
                return dp(s.get("added", ""))
            predicates.append(_added_rule)

        # ── text / substring rules ────────────────────────────────────────────
        elif key_lower == "artist":
            frag = expr.lower()
            def _artist_rule(p, m, a, s, f=frag):
                return f in (m.get("artist") or "").lower()
            predicates.append(_artist_rule)

        elif key_lower == "album":
            frag = expr.lower()
            def _album_rule(p, m, a, s, f=frag):
                return f in (m.get("album") or "").lower()
            predicates.append(_album_rule)

        elif key_lower == "genre":
            frag = expr.lower()
            def _genre_rule(p, m, a, s, f=frag):
                return f in (m.get("genre") or "").lower()
            predicates.append(_genre_rule)

        elif key_lower == "mood":
            val = expr.lower()
            def _mood_rule(p, m, a, s, v=val):
                return (a.get("mood") or "").lower() == v
            predicates.append(_mood_rule)

        elif key_lower == "key":
            frag = expr.lower()
            def _key_rule(p, m, a, s, f=frag):
                return f in (a.get("key") or m.get("key") or "").lower()
            predicates.append(_key_rule)

        elif key_lower == "energy":
            # energy:<mood_bucket>  — filters by heuristic mood label
            val = expr.lower()
            def _energy_rule(p, m, a, s, v=val):
                return (a.get("mood") or "").lower() == v
            predicates.append(_energy_rule)

        # ── listening-depth rules (from play_stats) ───────────────────────────

        elif key_lower in ("completion_rate", "completion"):
            num_pred = _parse_num_expr(expr)
            def _completion_rule(p, m, a, s, np=num_pred):
                return np(s.get("completion_rate", 0.0))
            predicates.append(_completion_rule)

        elif key_lower in ("skip_count", "skips"):
            num_pred = _parse_num_expr(expr)
            def _skip_rule(p, m, a, s, np=num_pred):
                return np(s.get("skip_count", 0))
            predicates.append(_skip_rule)

        elif key_lower == "played_mins":
            num_pred = _parse_num_expr(expr)
            def _mins_rule(p, m, a, s, np=num_pred):
                return np(s.get("played_seconds", 0.0) / 60.0)
            predicates.append(_mins_rule)

        elif key_lower == "played_secs":
            num_pred = _parse_num_expr(expr)
            def _secs_rule(p, m, a, s, np=num_pred):
                return np(s.get("played_seconds", 0.0))
            predicates.append(_secs_rule)

        elif key_lower == "elo":
            num_pred = _parse_num_expr(expr)
            def _elo_rule(p, m, a, s, np=num_pred):
                return np(s.get("elo_score", 1500.0))
            predicates.append(_elo_rule)

    return predicates


# ── smart playlist ─────────────────────────────────────────────────────────────

@dataclass
class SmartPlaylist:
    """
    A named playlist defined by a rules string.

    Rules string examples:
        "bpm:120-130 rating:>=3 sort=plays limit=20"
        "never-heard genre:electronic added:last-month"
        "artist:reznor sort=rating"
    """

    name:  str
    rules: str
    limit: int   = 100
    sort:  str   = "plays"    # plays | rating | added | random | title

    def __post_init__(self) -> None:
        # Parse sort= and limit= out of the rules string
        tokens = self.rules.split()
        remaining = []
        for t in tokens:
            if t.startswith("sort="):
                self.sort  = t[5:].lower()
            elif t.startswith("limit="):
                try:
                    self.limit = int(t[6:])
                except ValueError:
                    pass
            else:
                remaining.append(t)
        self.rules = " ".join(remaining)

    def evaluate(self, library) -> list[str]:
        """
        Return paths from *library* that match all rules, sorted and limited.
        """
        predicates = parse_rules(self.rules)
        results: list[str] = []

        for path in library.playlist:
            meta  = library.get_meta(path)       or {}
            ann   = library.get_annotation(path) or {}
            stats = library.get_stats(path)      or {}
            if all(p(path, meta, ann, stats) for p in predicates):
                results.append(path)

        results = _sort_results(results, self.sort, library)
        return results[:self.limit]

    def as_dict(self) -> dict:
        return {"name": self.name, "rules": self.rules,
                "limit": self.limit, "sort": self.sort}

    @classmethod
    def from_dict(cls, d: dict) -> "SmartPlaylist":
        return cls(name=d["name"], rules=d.get("rules", ""),
                   limit=d.get("limit", 100), sort=d.get("sort", "plays"))


def _sort_results(paths: list[str], sort_by: str, library) -> list[str]:
    if sort_by == "plays":
        return sorted(paths,
                      key=lambda p: -library.get_stats(p).get("plays", 0))
    if sort_by == "rating":
        return sorted(paths,
                      key=lambda p: (-library.get_stats(p).get("rating", 0),
                                     -library.get_stats(p).get("plays", 0)))
    if sort_by == "added":
        return sorted(paths,
                      key=lambda p: library.get_stats(p).get("added", ""),
                      reverse=True)
    if sort_by == "random":
        out = list(paths)
        random.shuffle(out)
        return out
    if sort_by == "title":
        return sorted(paths, key=lambda p: library.display_name(p).lower())
    if sort_by == "elo":
        return sorted(paths,
                      key=lambda p: -library.get_stats(p).get("elo_score", 1500.0))
    if sort_by == "completion":
        return sorted(paths,
                      key=lambda p: -library.get_stats(p).get("completion_rate", 0.0))
    if sort_by == "listened":
        return sorted(paths,
                      key=lambda p: -library.get_stats(p).get("played_seconds", 0.0))
    return paths


# ── Arc playlist ───────────────────────────────────────────────────────────────
#
# Generates an ordered track list that follows an energy arc shape (rising,
# falling, peak, valley, wave, flat) by greedily matching each arc-target
# position to the nearest-energy candidate in the library.
#
# Energy source priority per track (first non-None wins):
#   1. ann["d4a"]              — normalised D4 energy from ArcEngine history
#   2. ann["energy_heuristic"] — batch-extracted RMS estimate (0–1)
#   3. ann["spotify_energy"]   — Spotify audio feature (0–1)
#   4. 0.5                     — unknown, treat as mid-energy

ARC_TEMPLATES: dict[str, tuple[str, int]] = {
    "Rising Energy":   ("rising",  20),
    "Chill Evening":   ("falling", 20),
    "Workout Peak":    ("peak",    24),
    "Deep Focus":      ("flat",    20),
    "Morning Wave":    ("wave",    20),
    "Valley & Rise":   ("valley",  24),
    "Long Session":    ("rising",  40),
}
"""Preset name → (arc_shape, horizon) for common listening contexts."""


def _arc_targets(shape: str, horizon: int) -> list[float]:
    """Compute per-step energy targets ∈ [0, 1] for the given arc shape."""
    n = max(1, horizon)
    ts = [i / (n - 1) if n > 1 else 0.5 for i in range(n)]
    if shape == "rising":
        return ts
    if shape == "falling":
        return [1.0 - t for t in ts]
    if shape == "peak":
        return [4.0 * t * (1.0 - t) for t in ts]
    if shape == "valley":
        return [1.0 - 4.0 * t * (1.0 - t) for t in ts]
    if shape == "wave":
        return [(1.0 + math.sin(2.0 * math.pi * t - math.pi / 2.0)) / 2.0 for t in ts]
    # flat (default)
    return [0.5] * n


def _track_energy(path: str, library, meta_cache) -> float:
    """Return a normalised [0, 1] energy estimate for a single track."""
    ann: dict = {}
    if meta_cache is not None:
        try:
            ann = meta_cache.get_annotation(path) or {}
        except Exception:
            ann = library.get_annotation(path) or {}
    else:
        ann = library.get_annotation(path) or {}

    for key in ("d4a", "energy_heuristic", "spotify_energy"):
        v = ann.get(key)
        if v is not None:
            try:
                return max(0.0, min(1.0, float(v)))
            except (TypeError, ValueError):
                pass
    return 0.5


def arc_playlist(
    library,
    meta_cache=None,
    shape: str = "rising",
    horizon: int = 20,
    *,
    genre_filter: str | None = None,
    mood_filter: str | None = None,
    pool_factor: int = 3,
) -> tuple[list[str], str]:
    """Build an ordered playlist that follows an energy arc shape.

    Parameters
    ----------
    library:      phi Library instance (provides playlist + get_annotation).
    meta_cache:   Optional MetaCache — used when available for faster lookups.
    shape:        One of "rising", "falling", "peak", "valley", "wave", "flat".
    horizon:      Number of tracks in the output playlist.
    genre_filter: Restrict candidates to tracks whose genre contains this string
                  (case-insensitive substring match).
    mood_filter:  Restrict candidates to tracks with exactly this mood label.
    pool_factor:  At each step, sample the best track from the nearest
                  pool_factor candidates so consecutive picks aren't identical.

    Returns
    -------
    (paths, description)
        paths:       Ordered list of absolute track paths following the arc.
        description: Human-readable summary string for UI display.
    """
    shape = shape.lower().strip()
    if shape not in {"rising", "falling", "peak", "valley", "wave", "flat"}:
        shape = "rising"

    targets = _arc_targets(shape, horizon)

    # ── build candidate pool ──────────────────────────────────────────────────
    candidates: list[tuple[str, float]] = []  # (path, energy)
    for path in library.playlist:
        # genre filter
        if genre_filter:
            meta = library.get_meta(path) or {}
            genre_str = (meta.get("genre") or "").lower()
            if genre_filter.lower() not in genre_str:
                continue
        # mood filter
        if mood_filter:
            ann: dict = {}
            if meta_cache is not None:
                try:
                    ann = meta_cache.get_annotation(path) or {}
                except Exception:
                    ann = library.get_annotation(path) or {}
            else:
                ann = library.get_annotation(path) or {}
            track_mood = (ann.get("mood") or "").lower().strip()
            if track_mood != mood_filter.lower().strip():
                continue

        energy = _track_energy(path, library, meta_cache)
        candidates.append((path, energy))

    if not candidates:
        return [], "No matching tracks"

    # ── greedy arc walk ───────────────────────────────────────────────────────
    # At each step, pick from the `pool_factor` nearest-energy candidates to
    # add slight diversity without straying far from the arc target.
    remaining = list(candidates)
    result: list[str] = []

    for target in targets:
        if not remaining:
            break
        # Sort by distance to target; take top pool_factor, pick randomly
        remaining.sort(key=lambda x: abs(x[1] - target))
        pool_size = min(pool_factor, len(remaining))
        chosen = random.choice(remaining[:pool_size])
        result.append(chosen[0])
        remaining.remove(chosen)

    # ── build description ─────────────────────────────────────────────────────
    desc_parts = [f"{shape.title()} arc · {len(result)} tracks"]
    if genre_filter:
        desc_parts.append(f"genre:{genre_filter}")
    if mood_filter:
        desc_parts.append(f"mood:{mood_filter}")
    description = " · ".join(desc_parts)

    return result, description


@dataclass
class ArcSmartPlaylist:
    """A playlist defined by an energy arc shape rather than metadata rules.

    Compatible with SmartPlaylist.as_dict() / from_dict() serialisation so
    arc playlists can be saved and restored alongside rule-based ones.

    Examples
    --------
    >>> pl = ArcSmartPlaylist("Workout Peak", shape="peak", horizon=24)
    >>> paths, desc = pl.evaluate(library, meta_cache)
    """

    name:         str
    shape:        str  = "rising"   # rising | falling | peak | valley | wave | flat
    horizon:      int  = 20
    genre_filter: str | None = None
    mood_filter:  str | None = None
    pool_factor:  int  = 3

    def evaluate(self, library, meta_cache=None) -> tuple[list[str], str]:
        """Return (ordered_paths, description) for this arc shape."""
        return arc_playlist(
            library,
            meta_cache,
            shape=self.shape,
            horizon=self.horizon,
            genre_filter=self.genre_filter,
            mood_filter=self.mood_filter,
            pool_factor=self.pool_factor,
        )

    def as_dict(self) -> dict:
        return {
            "type":         "arc",
            "name":         self.name,
            "shape":        self.shape,
            "horizon":      self.horizon,
            "genre_filter": self.genre_filter,
            "mood_filter":  self.mood_filter,
            "pool_factor":  self.pool_factor,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ArcSmartPlaylist":
        return cls(
            name=d.get("name", "Arc Playlist"),
            shape=d.get("shape", "rising"),
            horizon=d.get("horizon", 20),
            genre_filter=d.get("genre_filter"),
            mood_filter=d.get("mood_filter"),
            pool_factor=d.get("pool_factor", 3),
        )

    @classmethod
    def from_template(cls, template_name: str) -> "ArcSmartPlaylist":
        """Construct from a named preset in ARC_TEMPLATES."""
        shape, horizon = ARC_TEMPLATES.get(template_name, ("rising", 20))
        return cls(name=template_name, shape=shape, horizon=horizon)
