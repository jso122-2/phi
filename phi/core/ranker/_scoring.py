"""Session-fit dimensions: genre, mood, novelty, ELO, phi_rank."""
from __future__ import annotations

import math
import pathlib
from datetime import datetime
from typing import TYPE_CHECKING

from phi.core.similarity import _cosine as _sim_cosine

from ._constants import (
    ELO_K,
    ELO_NORM_HI,
    ELO_NORM_LO,
    HELM_FLOOR,
    NOVELTY_HALF_LIFE,
    NOVELTY_NEVER_HEARD,
    _ASH_BASE,
    _ASH_K,
    _ASH_T_MIN,
)

if TYPE_CHECKING:
    from ._session import RankContext

# ── mood adjacency ─────────────────────────────────────────────────────────────

_MOOD_ADJACENT_DEFAULT: dict[str, set[str]] = {
    "calm": {"chill"},
    "chill": {"calm", "focused"},
    "focused": {"chill", "energetic", "happy"},
    "energetic": {"focused", "happy", "angry"},
    "happy": {"focused", "energetic"},
    "sad": {"calm", "chill"},
    "angry": {"energetic"},
}

# config/mood_adjacency.yaml lives three directories above this file:
#   phi/core/ranker/_scoring.py  →  ../../../config/mood_adjacency.yaml
_MOOD_ADJACENCY_YAML = (
    pathlib.Path(__file__).resolve().parents[3] / "config" / "mood_adjacency.yaml"
)


def _load_mood_adjacent() -> dict[str, set[str]]:
    """Load mood adjacency graph from YAML, falling back to the coded default."""
    if not _MOOD_ADJACENCY_YAML.exists():
        return _MOOD_ADJACENT_DEFAULT
    try:
        import yaml
        with _MOOD_ADJACENCY_YAML.open(encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        return {k: set(v or []) for k, v in raw.items() if isinstance(v, list)}
    except Exception:
        return _MOOD_ADJACENT_DEFAULT


_MOOD_ADJACENT: dict[str, set[str]] = _load_mood_adjacent()


def ash_yield(consecutive_coherent_plays: int) -> float:
    """Exponential ELO K for a coherent-session streak. Capped at ELO_K."""
    T = max(0, consecutive_coherent_plays - _ASH_T_MIN)
    return min(ELO_K, _ASH_BASE * math.exp(_ASH_K * T))


def _genre_affinity(meta: dict, ann: dict, ctx: "RankContext") -> float:
    """Genre match in [0, 1]: CLAP cosine, then tag Jaccard, then substring."""
    track_vec = ann.get("genre_vec")
    session_vec = ctx.__dict__.get("_session_genre_vec")
    if track_vec and session_vec:
        return _cosine(track_vec, session_vec)

    track_tags: set[str] = set()
    for t in (ann.get("mb_genres") or []):
        track_tags.add(str(t).lower())
    for t in (ann.get("lfm_tags") or []):
        track_tags.add(str(t).lower())
    single = (meta.get("genre") or ann.get("genre") or "").lower().strip()
    if single:
        track_tags.add(single)

    if ctx.session_tags and track_tags:
        session_set = set(ctx.session_tags)
        overlap = len(track_tags & session_set)
        union = len(track_tags | session_set)
        jaccard = overlap / union if union else 0.0
        return 0.20 + 0.80 * jaccard

    if not ctx.session_genre:
        return 0.50
    if not track_tags and not single:
        return 0.40

    sg = ctx.session_genre
    if sg in single or single in sg:
        return 1.0
    for t in track_tags:
        if sg in t or t in sg:
            return 0.80
    return 0.20


def _mood_affinity(ann: dict, meta: dict, ctx: "RankContext") -> float:
    """Mood match in [0, 1]: CLAP cosine, then valence/energy, then label."""
    track_vec = ann.get("mood_vec")
    session_vec = ctx.__dict__.get("_session_mood_vec")
    if track_vec and session_vec:
        return _cosine(track_vec, session_vec)

    track_valence = ann.get("spotify_valence")
    track_energy = ann.get("spotify_energy")
    if (
        track_valence is not None
        and track_energy is not None
        and ctx.session_valence is not None
        and ctx.session_energy is not None
    ):
        dv = float(track_valence) - ctx.session_valence
        de = float(track_energy) - ctx.session_energy
        dist = math.sqrt(dv * dv + de * de) / math.sqrt(2.0)
        return round(max(0.0, 1.0 - dist), 4)

    if not ctx.session_mood:
        return 0.50
    track_mood = (
        ann.get("spotify_mood") or ann.get("mood") or meta.get("mood") or ""
    ).lower().strip()
    if not track_mood:
        return 0.40
    if track_mood == ctx.session_mood:
        return 1.0
    if track_mood in _MOOD_ADJACENT.get(ctx.session_mood, set()):
        return 0.65
    return 0.15


def _novelty_score(stats: dict) -> float:
    """Freshness in [0, 1]. Unplayed tracks get NOVELTY_NEVER_HEARD."""
    last_played = stats.get("last_played")
    if not last_played:
        return NOVELTY_NEVER_HEARD
    try:
        last_dt = datetime.fromisoformat(last_played)
    except (ValueError, TypeError):
        return NOVELTY_NEVER_HEARD
    days = (datetime.now() - last_dt).total_seconds() / 86400.0
    score = 1.0 - math.exp(-days * math.log(2) / NOVELTY_HALF_LIFE)
    return round(min(1.0, score), 4)


def _elo_normalised(elo: float) -> float:
    """Map ELO from [ELO_NORM_LO, ELO_NORM_HI] onto [0, 1]."""
    return max(0.0, min(1.0, (elo - ELO_NORM_LO) / (ELO_NORM_HI - ELO_NORM_LO)))


def _phi_rank(ann: dict) -> float:
    """RankArm score from annotations, or 0.5 if missing."""
    v = ann.get("phi_rank")
    if v is None:
        return 0.5
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.5


def _confidence_weights(ann: dict, base: dict) -> dict:
    """Return weights scaled by buoyancy so helm dims never hand off to ELO/novelty.

    Reads ``buoyancy`` from annotations when written by enrich_daemon (Step 8);
    falls back to ``meta_score`` for tracks that have not been enriched yet.

    Helm dims (genre, mood, phi_rank) scale with buoyancy but are floored at
    HELM_FLOOR × base — this prevents ELO/novelty from inflating via
    renormalisation when enrichment is sparse (skip-spiral guard).

    meta_score ∈ [0, 1] — legacy fallback only.
    buoyancy   ∈ [0, 1] — coverage × agreement; preferred signal.
    """
    raw = ann.get("buoyancy") if ann.get("buoyancy") is not None else ann.get("meta_score")
    buoy = max(0.0, min(1.0, float(raw) if raw is not None else 0.5))

    # Helm dims: floor ensures they never fall below half their configured share.
    helm_scale = max(HELM_FLOOR, buoy)
    w = {
        "genre":    base["genre"]    * helm_scale,
        "mood":     base["mood"]     * helm_scale,
        "novelty":  base["novelty"],               # flat — not a catalog signal
        "elo":      base["elo"],                   # flat — not a catalog signal
        "phi_rank": base["phi_rank"] * helm_scale,
    }
    total = sum(w.values())
    return {k: v / total for k, v in w.items()} if total > 0 else base


def _plurality(items: list[str]) -> str | None:
    """Most common string in *items*, or None if empty."""
    if not items:
        return None
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return max(counts, key=lambda k: counts[k])


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine in [0, 1]; 0.5 on empty, mismatch, or NaN."""
    if not a or not b or len(a) != len(b):
        return 0.5
    v = _sim_cosine(a, b)
    return max(0.0, min(1.0, v)) if v == v else 0.5
