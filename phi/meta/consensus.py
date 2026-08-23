# -*- coding: utf-8 -*-
"""phi.meta.consensus — cross-source metadata reconciliation.

Computes consensus fields from multiple enrichment sources once all
individual source passes are complete.

Functions
---------
bpm_consensus(ann, meta)  → dict   bpm_consensus, bpm_confidence, bpm_sources
genre_consensus(ann, meta) → dict  genre_consensus (list[str], up to 5)
meta_score(ann, meta)      → dict  meta_score (float 0–1), meta_fields_present (int)

All functions return a flat dict ready to merge into an annotation store.
They never raise — failures return empty dicts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ── BPM consensus ─────────────────────────────────────────────────────────────

# Source weight: higher = more trusted
_BPM_WEIGHTS = {
    "spotify": 3,
    "deezer":  2,
    "librosa": 1,
}

# librosa frequently returns half-time or double-time estimates.
# Spotify and Deezer are generally in the "correct" octave.
# If librosa's value is within 5% of half or double another source,
# adjust it.
_OCTAVE_TOL = 0.05


def _octave_correct(bpm_to_fix: float, reference: float) -> float:
    """
    Return bpm_to_fix adjusted to the closest octave-consistent value
    relative to *reference* (×0.5 or ×2 correction).
    """
    candidates = [bpm_to_fix, bpm_to_fix * 2, bpm_to_fix / 2]
    return min(candidates, key=lambda c: abs(c - reference))


def bpm_consensus(ann: dict, meta: dict) -> dict:
    """
    Compute a weighted consensus BPM from all available sources.

    Sources checked (in weight order):
      spotify_tempo  (Spotify API — very reliable)
      deezer_bpm     (Deezer API)
      bpm            (librosa beat tracker — prone to octave errors)

    Algorithm:
      1. Collect non-zero values from each source.
      2. If librosa's value is near a 2× or 0.5× octave of a higher-weight
         source, snap it to the consistent octave.
      3. Compute a weighted mean of all corrected values.
      4. Confidence = 1.0 − (std / mean) clamped to [0, 1].  High confidence
         means sources agree.

    Returns keys: bpm_consensus, bpm_confidence, bpm_sources (list of names).
    """
    readings: list[tuple[str, float]] = []  # (source_name, bpm_value)

    sp_bpm = float(ann.get("spotify_tempo") or 0.0)
    dz_bpm = float(ann.get("deezer_bpm")    or 0.0)
    # librosa_bpm (signal-derived) takes priority over the file tag BPM
    lr_bpm = float(ann.get("librosa_bpm") or meta.get("bpm") or ann.get("bpm") or 0.0)

    if sp_bpm > 20:
        readings.append(("spotify", sp_bpm))
    if dz_bpm > 20:
        readings.append(("deezer", dz_bpm))
    if lr_bpm > 20:
        # Octave-correct librosa against the best available reference
        ref = sp_bpm if sp_bpm > 20 else (dz_bpm if dz_bpm > 20 else lr_bpm)
        corrected = _octave_correct(lr_bpm, ref) if ref != lr_bpm else lr_bpm
        readings.append(("librosa", corrected))

    if not readings:
        return {}

    # Weighted mean
    total_w = sum(_BPM_WEIGHTS.get(src, 1) for src, _ in readings)
    w_mean  = sum(_BPM_WEIGHTS.get(src, 1) * bpm for src, bpm in readings) / total_w

    # Confidence: 1 − normalised std (higher = sources agree more)
    if len(readings) > 1:
        variance = sum(
            _BPM_WEIGHTS.get(src, 1) * (bpm - w_mean) ** 2
            for src, bpm in readings
        ) / total_w
        std = variance ** 0.5
        confidence = max(0.0, min(1.0, 1.0 - std / max(w_mean, 1.0)))
    else:
        confidence = 0.6   # single source: moderate confidence

    return {
        "bpm_consensus":  round(w_mean, 2),
        "bpm_confidence": round(confidence, 3),
        "bpm_sources":    [src for src, _ in readings],
    }


# ── Genre consensus ────────────────────────────────────────────────────────────

# Normalisation map: raw tag → canonical label
_GENRE_NORM: dict[str, str] = {
    "hip-hop":        "hip hop",
    "hip hop/rap":    "hip hop",
    "rap":            "hip hop",
    "r&b":            "r&b",
    "rhythm & blues": "r&b",
    "rhythm and blues":"r&b",
    "rnb":            "r&b",
    "indie rock":     "indie",
    "indie pop":      "indie",
    "alternative rock":"alternative",
    "alt rock":       "alternative",
    "alt-rock":       "alternative",
    "classical":      "classical",
    "orchestral":     "classical",
    "drum and bass":  "dnb",
    "drum & bass":    "dnb",
    "d&b":            "dnb",
    "electronica":    "electronic",
    "electro":        "electronic",
    "edm":            "electronic",
    "dance":          "electronic",
    "techno":         "techno",
    "house":          "house",
    "deep house":     "house",
    "tech house":     "house",
}

# Junk tags to exclude from genre consensus
_GENRE_EXCLUDE = frozenset({
    "", "unknown", "other", "various", "miscellaneous", "seen live",
    "albums i own", "favorites", "love", "good", "best", "awesome",
    "music", "audio", "songs",
})

# Source weight: higher = more authoritative genre label
_GENRE_SOURCE_WEIGHTS = {
    "mb_genres":      3,   # MusicBrainz community tags
    "lfm_tags":       3,   # Last.fm community tags
    "discogs_styles": 2,   # Discogs styles (more specific)
    "discogs_genres": 1,   # Discogs genres (broad)
    "octopus_tags":   1,   # OctopusTracer model-suggested tags (mood + genre arm)
    "genre":          1,   # file-embedded tag (often wrong or vague)
}


def _norm_genre(raw: str) -> str:
    s = raw.strip().lower()
    return _GENRE_NORM.get(s, s)


def genre_consensus(ann: dict, meta: dict) -> dict:
    """
    Merge genre/tag data from all sources into a ranked list.

    Source priority (highest first): MusicBrainz tags, Last.fm tags,
    Discogs styles, Discogs genres, embedded file tag.

    Returns key: genre_consensus (list of up to 5 canonical genre strings).
    """
    scores: dict[str, float] = {}

    def _add(source: str, tags) -> None:
        w = _GENRE_SOURCE_WEIGHTS.get(source, 1)
        if isinstance(tags, str):
            tags = [tags]
        if not tags:
            return
        for i, raw in enumerate(tags):
            g = _norm_genre(str(raw))
            if g and g not in _GENRE_EXCLUDE and len(g) <= 40:
                # Earlier in the list → higher position bonus
                position_bonus = 1.0 / (1 + i)
                scores[g] = scores.get(g, 0.0) + w * position_bonus

    _add("mb_genres",      ann.get("mb_genres"))
    _add("lfm_tags",       ann.get("lfm_tags"))
    _add("discogs_styles", ann.get("discogs_styles"))
    _add("discogs_genres", ann.get("discogs_genres"))
    _add("octopus_tags",   ann.get("octopus_tags"))
    _add("genre",          meta.get("genre") or ann.get("genre"))

    if not scores:
        return {}

    ranked = sorted(scores, key=lambda g: -scores[g])[:5]
    return {"genre_consensus": ranked}


# ── Metadata completeness score ────────────────────────────────────────────────

# (field_name, where_to_look, weight)
# where_to_look: "meta" | "ann" | "either"
_SCORE_FIELDS: list[tuple[str, str, float]] = [
    # Core identity
    ("title",           "meta",   1.0),
    ("artist",          "meta",   1.0),
    ("album",           "meta",   0.5),
    ("year",            "meta",   0.5),
    ("genre",           "either", 0.5),
    ("art_bytes",       "meta",   0.5),
    # Acoustic data
    ("bpm_consensus",   "ann",    1.0),
    ("bpm",             "either", 0.5),   # partial credit without consensus
    ("duration",        "meta",   0.5),
    # Source enrichment flags (quality indicators)
    ("mb_enriched",     "ann",    1.5),
    ("spotify_enriched","ann",    1.5),
    ("lfm_enriched",    "ann",    1.0),
    ("discogs_enriched","ann",    1.0),
    ("deezer_enriched",   "ann",    0.5),
    ("librosa_enriched",  "ann",    0.5),
    # Rich metadata
    ("genre_consensus", "ann",    1.0),
    ("spotify_valence", "ann",    0.5),
    ("spotify_energy",  "ann",    0.5),
    ("lfm_tags",        "ann",    0.5),
    ("discogs_styles",  "ann",    0.5),
    ("mb_artist_area",  "ann",    0.5),
    ("isrc",            "either", 0.5),
    ("lyrics_enriched", "ann",    0.5),
    ("composer",        "either", 0.5),
]

_MAX_SCORE = sum(w for _, _, w in _SCORE_FIELDS)


def meta_score(ann: dict, meta: dict) -> dict:
    """
    Compute a metadata completeness score (0.0–1.0) for a track.

    Higher = more enrichment sources have contributed usable data.
    Useful for filtering low-quality records out of ML training sets.

    Returns keys: meta_score (float), meta_fields_present (int).
    """
    earned = 0.0
    present = 0

    for field, where, weight in _SCORE_FIELDS:
        val = None
        if where in ("meta", "either"):
            val = (meta or {}).get(field)
        if val is None and where in ("ann", "either"):
            val = (ann or {}).get(field)

        if val is not None and val is not False and val != "" and val != []:
            earned  += weight
            present += 1

    return {
        "meta_score":          round(earned / _MAX_SCORE, 3),
        "meta_fields_present": present,
    }


# ── Buoyancy ───────────────────────────────────────────────────────────────────

# Catalog arms counted toward coverage (Deezer / librosa are instruments, not catalog).
_CATALOG_FLAGS: tuple[str, ...] = (
    "spotify_enriched",
    "mb_enriched",
    "lfm_enriched",
    "discogs_enriched",
)


def buoyancy_score(ann: dict, meta: dict) -> float:
    """Compute buoyancy: catalog coverage × cross-source agreement ∈ [0, 1].

    High buoyancy → helm (genre, mood, BPM, key) owns next-track and ring heading.
    Low buoyancy  → dampen helm authority; do NOT hand off to ELO/novelty.

    Coverage  = catalog arms present / 4  (Spotify, MusicBrainz, Last.fm, Discogs).
    Agreement = weighted mean of per-field agreement signals (BPM, mood, genre).
    buoyancy  = (coverage + agreement) / 2, clamped to [0, 1].
    """
    n_sources = sum(1 for f in _CATALOG_FLAGS if ann.get(f))
    coverage = n_sources / len(_CATALOG_FLAGS)

    if coverage == 0.0:
        return 0.0

    agreement_signals: list[float] = []

    # BPM agreement — bpm_confidence already encodes cross-source spread.
    bpm_conf = ann.get("bpm_confidence")
    if bpm_conf is not None:
        agreement_signals.append(float(bpm_conf))

    # Mood agreement — Spotify numeric label + Last.fm tag corroboration.
    sp_mood = ann.get("spotify_mood") or ""
    lfm_tags: list[str] = [t.lower() for t in (ann.get("lfm_tags") or [])]
    if sp_mood and lfm_tags:
        confirms = any(sp_mood in t or t in sp_mood for t in lfm_tags)
        agreement_signals.append(1.0 if confirms else 0.60)
    elif sp_mood:
        agreement_signals.append(0.70)  # single source, no corroboration

    # Genre agreement — more ranked genres = more cross-source consensus.
    genre_list: list[str] = ann.get("genre_consensus") or []
    if len(genre_list) >= 3:
        agreement_signals.append(1.0)
    elif len(genre_list) == 2:
        agreement_signals.append(0.70)
    elif len(genre_list) == 1:
        agreement_signals.append(0.40)
    # No genre_consensus → no signal (neutral, not penalised)

    agreement = (
        sum(agreement_signals) / len(agreement_signals)
        if agreement_signals
        else 0.0   # no signals → no agreement credit; coverage still contributes
    )

    return round(max(0.0, min(1.0, (coverage + agreement) / 2.0)), 3)


# ── ConsensusTrack ─────────────────────────────────────────────────────────────

@dataclass
class ConsensusTrack:
    """Single source of truth assembled from all catalog enrichment arms.

    The two jobs:
      helm      — what pilots the ship: identity, BPM, key, mood, genre.
      buoyancy  — how much authority the helm gets ∈ [0, 1].
                  High → helm owns next-track, ring inject, UI grouping.
                  Low  → reduce heading authority; enrich daemon is the bilge pump.

    Built by ``build_consensus_track(ann, meta)``; consumed by TrackRanker,
    FoldInjector, and any downstream that currently reads raw ann/meta dicts.
    """

    # ── identity ──────────────────────────────────────────────────────────────
    title:  str = ""
    artist: str = ""
    album:  str = ""
    isrc:   str = ""

    # ── helm numerics ─────────────────────────────────────────────────────────
    bpm:            float      = 0.0
    bpm_confidence: float      = 0.0
    key:            str        = ""
    key_camelot:    str        = ""
    valence:        float      = 0.0   # Spotify; 0.0 = unknown
    energy:         float      = 0.0   # Spotify; 0.0 = unknown
    mood:           str        = ""    # derived label (spotify_mood → fallback)
    genre:          list[str]  = field(default_factory=list)  # ranked consensus

    # ── buoyancy ──────────────────────────────────────────────────────────────
    buoyancy:     float      = 0.0   # coverage × agreement ∈ [0, 1]
    source_count: int        = 0     # catalog sources that contributed
    agreement:    float      = 0.0   # cross-source agreement signal
    sources:      list[str]  = field(default_factory=list)  # which arms contributed


def build_consensus_track(ann: dict, meta: dict) -> ConsensusTrack:
    """Assemble a ConsensusTrack from raw annotation and meta dicts.

    Reads pre-computed consensus fields when present (written by enrich_daemon
    Step 8); computes them on-the-fly for tracks that have not yet been
    enriched.

    Parameters
    ----------
    ann  : annotation dict from ``Library.annotations[path]``
    meta : meta dict from ``Library.meta_cache[path]``

    Returns
    -------
    ConsensusTrack — spine object for ranker, fold injector, and UI.
    """
    # BPM — use precomputed if available, else compute now.
    if "bpm_consensus" in ann:
        bpm_val  = float(ann["bpm_consensus"] or 0.0)
        bpm_conf = float(ann.get("bpm_confidence") or 0.0)
    else:
        bpm_result = bpm_consensus(ann, meta)
        bpm_val  = float(bpm_result.get("bpm_consensus") or 0.0)
        bpm_conf = float(bpm_result.get("bpm_confidence") or 0.0)

    # Genre — same pattern.
    if "genre_consensus" in ann:
        genre_list: list[str] = list(ann["genre_consensus"] or [])
    else:
        genre_list = list(genre_consensus(ann, meta).get("genre_consensus") or [])

    # Buoyancy — prefer stored value; agree signal from annotation state.
    raw_buoy = ann.get("buoyancy")
    buoy = float(raw_buoy) if raw_buoy is not None else buoyancy_score(ann, meta)

    contributing = [
        s for s, key in {
            "spotify":     "spotify_enriched",
            "musicbrainz": "mb_enriched",
            "lastfm":      "lfm_enriched",
            "discogs":     "discogs_enriched",
        }.items()
        if ann.get(key)
    ]

    return ConsensusTrack(
        title  = str(meta.get("title")  or ann.get("title")  or ""),
        artist = str(meta.get("artist") or ann.get("artist") or ""),
        album  = str(meta.get("album")  or ann.get("album")  or ""),
        isrc   = str(ann.get("isrc")    or meta.get("isrc")  or ""),
        bpm            = bpm_val,
        bpm_confidence = bpm_conf,
        key         = str(meta.get("key")         or ann.get("mb_key")         or ""),
        key_camelot = str(meta.get("key_camelot") or ann.get("mb_key_camelot") or ""),
        valence  = float(ann.get("spotify_valence") or 0.0),
        energy   = float(ann.get("spotify_energy")  or 0.0),
        mood     = str(ann.get("spotify_mood") or ann.get("mood") or meta.get("mood") or ""),
        genre    = genre_list,
        buoyancy     = buoy,
        source_count = len(contributing),
        agreement    = bpm_conf or 0.5,
        sources      = contributing,
    )
