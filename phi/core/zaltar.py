# -*- coding: utf-8 -*-
"""phi.core.zaltar — reverse-Zaltar text-to-playlist engine.

User types a mood, concept, or free text.  Zaltar encodes it with CLAP's
text encoder, searches the library's CLAP audio vectors for the closest
matches, blends in D4 personalisation, and returns 5 tracks ordered for
a smooth mix.

API
---
    from phi.core.zaltar import zaltar_query

    results = zaltar_query("feeling melancholic, 3am, rain on a window", library)
    # → [{"path", "title", "artist", "similarity", "d4", "bpm", "mix_pos"}, ...]

Fallback
--------
If CLAP is not loaded / cached locally, text_to_vec() returns None and
zaltar_query falls back to a D4-ranked sample from the library
(personalised by listening history only).
"""
from __future__ import annotations

import itertools
import logging
import math
import os
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from phi.core.library import Library

log = logging.getLogger("phi.zaltar")

# Weight blend: cosine-similarity vs D4 personalisation
_SIM_WEIGHT = 0.75
_D4_WEIGHT  = 0.25

# How many CLAP candidates to retrieve before re-scoring + ordering
_POOL = 30


# ── text → CLAP vector ────────────────────────────────────────────────────────

def text_to_vec(text: str) -> Optional[list[float]]:
    """
    Encode arbitrary text through the CLAP text encoder.

    Returns a L2-normalised 512-d float list, or None if CLAP is not
    available (model not locally cached, or torch/transformers absent).

    The CLAP model is loaded lazily on first call and kept in process
    memory — same singleton used by CLAPModel for audio encoding.
    """
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    try:
        import torch
        from transformers import ClapModel, ClapProcessor
    except ImportError:
        log.debug("zaltar: torch/transformers not installed")
        return None

    try:
        proc = ClapProcessor.from_pretrained(
            "laion/clap-htsat-fused", local_files_only=True
        )
        model = ClapModel.from_pretrained(
            "laion/clap-htsat-fused", local_files_only=True
        )
        model.eval()
    except Exception as exc:
        log.debug("zaltar: CLAP model not locally cached — %s", exc)
        return None

    try:
        with torch.no_grad():
            inputs = proc(text=[text], return_tensors="pt", padding=True)
            vec = model.get_text_features(**inputs)
            vec = vec / vec.norm(dim=-1, keepdim=True)
        return vec[0].tolist()
    except Exception as exc:
        log.warning("zaltar: text encoding failed — %s", exc)
        return None


# ── D4 score lookup ───────────────────────────────────────────────────────────

def _d4_for(path: str, library: "Library") -> float:
    """Return D4 score [0,1] from annotations, or neutral 0.5."""
    ann = library.annotations.get(path) or {}
    v = ann.get("d4")
    if v is not None:
        try:
            return float(v)
        except (TypeError, ValueError):
            pass
    return 0.5


def _bpm_for(path: str, library: "Library") -> Optional[float]:
    """Return BPM from annotations/meta, or None."""
    ann  = library.annotations.get(path) or {}
    meta = library.meta_cache.get(path)   or {}
    for key in ("bpm_consensus", "bpm", "deezer_bpm"):
        v = ann.get(key) or meta.get(key)
        if v is not None:
            try:
                f = float(v)
                if 40.0 < f < 300.0:
                    return f
            except (TypeError, ValueError):
                pass
    return None


# ── mix ordering ──────────────────────────────────────────────────────────────

def mix_order(candidates: list[dict]) -> list[dict]:
    """
    Order up to 5 tracks for a smooth mix.

    Strategy: enumerate all permutations (≤5! = 120) and pick the ordering
    that minimises total BPM distance between adjacent tracks.  Tracks with
    no BPM fall back to neutral 120 BPM for ordering purposes only.

    Returns the same dicts with 'mix_pos' (1-indexed) added.
    """
    if len(candidates) <= 1:
        for i, t in enumerate(candidates):
            t["mix_pos"] = i + 1
        return candidates

    bpms = [t.get("bpm") or 120.0 for t in candidates]

    def arc_cost(perm: tuple[int, ...]) -> float:
        cost = 0.0
        for a, b in zip(perm, perm[1:]):
            cost += abs(bpms[a] - bpms[b])
        return cost

    best_perm = min(
        itertools.permutations(range(len(candidates))),
        key=arc_cost,
    )

    ordered = [candidates[i] for i in best_perm]
    for i, t in enumerate(ordered):
        t["mix_pos"] = i + 1
    return ordered


# ── main API ──────────────────────────────────────────────────────────────────

def zaltar_query(
    text:       str,
    library:    "Library",
    *,
    n:          int   = 5,
    d4_weight:  float = _D4_WEIGHT,
    sim_weight: float = _SIM_WEIGHT,
) -> list[dict]:
    """
    Encode *text* and return *n* library tracks as mix-ordered dicts.

    Each dict contains:
        path        absolute path
        title       track title (or filename)
        artist      artist name
        similarity  CLAP cosine similarity [−1, 1]  (0.5 if CLAP unavailable)
        d4          D4 score [0, 1]
        bpm         BPM (float or None)
        blend_score weighted combination used for ranking
        mix_pos     1-based position in mix order

    When CLAP is available the result is text-semantics first, personalised
    by D4.  When CLAP is absent it falls back to a D4-ranked slice of the
    most-played tracks, giving a personalised result with no text signal.
    """
    from phi.core.similarity import find_similar_to_vec

    if not library.playlist:
        return []

    # ── 1. encode text ────────────────────────────────────────────────────────
    query_vec = text_to_vec(text)
    clap_available = query_vec is not None

    # ── 2. retrieve candidates ────────────────────────────────────────────────
    if clap_available:
        pool_size = min(_POOL, len(library.playlist))
        raw = find_similar_to_vec(query_vec, library, n=pool_size, vec_key="mood_vec")
        # raw → [(path, cosine_sim), ...]
    else:
        # Fallback: rank by D4 × play-weight from play_stats
        log.info("zaltar: CLAP unavailable — falling back to D4+plays ranking")
        raw = _d4_fallback(library, n=_POOL)

    if not raw:
        return []

    # ── 3. blend score ────────────────────────────────────────────────────────
    pool: list[dict] = []
    for path, sim in raw:
        d4 = _d4_for(path, library)
        # Normalise cosine sim from [-1,1] to [0,1]
        sim_norm = (sim + 1.0) / 2.0 if clap_available else 0.5
        blend = sim_weight * sim_norm + d4_weight * d4
        meta  = library.meta_cache.get(path) or {}
        fname = os.path.basename(path)
        title  = meta.get("title")  or os.path.splitext(fname)[0]
        artist = meta.get("artist") or "—"
        pool.append({
            "path":        path,
            "title":       title,
            "artist":      artist,
            "similarity":  round(sim, 4),
            "d4":          round(d4, 4),
            "bpm":         _bpm_for(path, library),
            "blend_score": round(blend, 4),
            "mix_pos":     0,
        })

    # ── 4. top-n by blend score ───────────────────────────────────────────────
    pool.sort(key=lambda t: -t["blend_score"])
    top = pool[:n]

    # ── 5. mix order ──────────────────────────────────────────────────────────
    return mix_order(top)


# ── D4 fallback (no CLAP) ─────────────────────────────────────────────────────

def _d4_fallback(library: "Library", n: int) -> list[tuple[str, float]]:
    """
    When CLAP is unavailable rank by D4 * personalisation_weight.

    personalisation_weight = (1 + log1p(plays)) * completion_rate
    Both default to 1.0 for unplayed tracks so they can still surface.
    """
    results: list[tuple[str, float]] = []
    for path in library.playlist:
        d4    = _d4_for(path, library)
        stats = library.play_stats.get(path) or {}
        plays = float(stats.get("plays", 0) or 0)
        cr    = float(stats.get("completion_rate", 1.0) or 1.0)
        w     = (1.0 + math.log1p(plays)) * max(0.1, cr)
        results.append((path, d4 * w))
    results.sort(key=lambda t: -t[1])
    return results[:n]
