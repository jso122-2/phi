# -*- coding: utf-8 -*-
"""phi.engine.playlist_studio — ML-guided playlist building studio.

Architecture
------------
Seed-and-grow traversal guided by a user-chosen arc shape.

The studio builds a playlist of *target_count* tracks in one shot:

    1. Start from 1–5 seed tracks supplied by the user.
    2. Maintain a *frontier vector* — the CLAP-space centroid of the tracks
       picked so far (exponential moving average, α = 0.30).
    3. At each slot, pull a candidate pool from ``find_similar_to_vec``
       (CAIRRN MATH-gated, falls back to BPM when no vectors present).
    4. Score each candidate on two dimensions:
         arc_score   — Gaussian proximity to the arc's energy target at
                       this slot position.  Uses the same formula as
                       ArcEngine.target() so shapes are identical.
         trans_score — cosine similarity to the last added track, with a
                       penalty if the jump exceeds the transition_threshold.
       Combined: arc_weight × arc_score  +  sim_weight × sim × trans_score
    5. Apply diversity gates before accepting a pick:
         max_per_artist       — default 2
         max_per_genre        — default 3
    6. Add the best pick, update the frontier EMA, advance.

Fallback
--------
When a track has no CLAP mood_vec, its energy is estimated from
``spotify_energy`` → ``spotify_valence`` → 0.5 (neutral).  BPM proximity
replaces cosine similarity for the whole library when nothing is annotated.

CAIRRN integration
------------------
``PlaylistStudio.build()`` signals the ForestFloor via ``studio_build(n)``
before starting.  This routes a PLAYLIST_BUILD event through the MATH hub
(same shard as SIMILARITY_SEARCH) so the similarity index is warm and the
hub's coherence state reflects the upcoming embedding scan.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import numpy as np

from phi.engine.arc_engine import ArcShape

if TYPE_CHECKING:
    from phi.core.library import Library
    from phi.engine.forest_floor import ForestFloor

_log = logging.getLogger("phi.studio")


# ── StudioRequest ─────────────────────────────────────────────────────────────

@dataclass
class StudioRequest:
    """Parameters for a single playlist-build run.

    Attributes
    ----------
    seeds               1–5 anchor track paths (included at the front).
    arc_shape           Energy arc shape over the playlist horizon.
    target_count        Stop when the playlist reaches this many tracks.
    max_per_artist      Diversity gate: skip track if artist already appears
                        this many times in the growing playlist.
    max_per_genre       Diversity gate: same for genre/genre-cluster label.
    transition_threshold  Cosine delta above this is considered a jarring jump
                        and is penalised (score × 0.4).
    candidate_pool      How many similarity candidates to evaluate at each step.
    arc_weight          Weight for the arc-fit score in the combined objective.
    sim_weight          Weight for the graph-similarity × transition score.
    arc_sharpness       Gaussian sharpness k — larger = harder constraint on arc.
    """
    seeds:                list[str]
    arc_shape:            ArcShape = ArcShape.FLAT
    target_count:         int      = 20
    max_per_artist:       int      = 2
    max_per_genre:        int      = 3
    transition_threshold: float    = 0.60
    candidate_pool:       int      = 15
    arc_weight:           float    = 0.60
    sim_weight:           float    = 0.40
    arc_sharpness:        float    = 20.0


# ── StudioResult ──────────────────────────────────────────────────────────────

@dataclass
class StudioResult:
    """Output of a completed PlaylistStudio.build() run.

    Attributes
    ----------
    tracks              Ordered list of absolute paths (seeds + grown tracks).
    arc_targets         Target energy [0, 1] at each playlist position.
    arc_scores          How well each track matched its arc target (0–1).
    transition_scores   Cosine similarity between adjacent track pairs.
    seed_paths          The seeds supplied in the StudioRequest.
    arc_shape           Shape name used.
    n_annotated         Tracks with CLAP mood_vec present.
    n_fallback          Tracks that used metadata energy fallback.
    """
    tracks:            list[str]
    arc_targets:       list[float]
    arc_scores:        list[float]
    transition_scores: list[float]
    seed_paths:        list[str]
    arc_shape:         str
    n_annotated:       int = 0
    n_fallback:        int = 0

    @property
    def mean_arc_score(self) -> float:
        return float(np.mean(self.arc_scores)) if self.arc_scores else 0.0

    @property
    def mean_transition(self) -> float:
        return float(np.mean(self.transition_scores)) if self.transition_scores else 0.0

    def summary(self) -> str:
        return (
            f"StudioResult  tracks={len(self.tracks)}/{len(self.seed_paths)} seeds"
            f"  arc={self.arc_shape}  mean_arc={self.mean_arc_score:.3f}"
            f"  mean_trans={self.mean_transition:.3f}"
            f"  annotated={self.n_annotated}  fallback={self.n_fallback}"
        )


# ── PlaylistStudio ────────────────────────────────────────────────────────────

class PlaylistStudio:
    """Arc-steered seed-and-grow playlist builder.

    Parameters
    ----------
    library     Live phi Library instance (tracks + annotations).
    floor       Optional ForestFloor — used to signal CAIRRN before build
                so the MATH hub's similarity index is warm.
    """

    def __init__(
        self,
        library:  "Library",
        floor:    "Optional[ForestFloor]" = None,
    ) -> None:
        self._library = library
        self._floor   = floor

    # ── Public API ────────────────────────────────────────────────────────────

    def build(self, request: StudioRequest) -> StudioResult:
        """Build a playlist from the given StudioRequest.

        The seeds are always placed first.  The studio then grows the list
        to ``request.target_count`` by picking the best-scoring candidate
        at each step.

        Returns
        -------
        StudioResult with the ordered track list and per-track scores.
        """
        seeds = [s for s in request.seeds if s in set(self._library.playlist)]
        if not seeds:
            _log.warning("PlaylistStudio.build: no valid seeds in library")
            return StudioResult(
                tracks=[], arc_targets=[], arc_scores=[],
                transition_scores=[], seed_paths=request.seeds,
                arc_shape=request.arc_shape.value,
            )

        # Signal CAIRRN so MATH hub similarity index is pre-warmed
        if self._floor is not None:
            try:
                self._floor.studio_build(request.target_count)
            except Exception:
                pass

        playlist: list[str]   = list(seeds)
        used:     set[str]    = set(playlist)
        arc_targets:  list[float] = []
        arc_scores:   list[float] = []
        trans_scores: list[float] = []
        n_annotated = 0
        n_fallback  = 0

        # Seed arc scores (position 0..len(seeds)-1)
        for i, path in enumerate(seeds):
            tgt = _arc_target(request.arc_shape, i, request.target_count)
            eng = self._track_energy(path)
            arc_targets.append(tgt)
            arc_scores.append(_gaussian_score(eng, tgt, request.arc_sharpness))
            if self._has_vec(path):
                n_annotated += 1
            else:
                n_fallback += 1

        # Seed transition scores (gap between each adjacent seed pair)
        for i in range(1, len(seeds)):
            trans_scores.append(self._cosine_pair(seeds[i - 1], seeds[i]))

        # Frontier: EMA of seed embedding vectors
        frontier_vec = self._centroid(seeds)

        # ── Grow ──────────────────────────────────────────────────────────────
        for slot in range(len(seeds), request.target_count):
            tgt = _arc_target(request.arc_shape, slot, request.target_count)

            candidates = self._get_candidates(
                frontier_vec=frontier_vec,
                used=used,
                pool_size=request.candidate_pool * 3,
                last_path=playlist[-1] if playlist else None,
            )
            if not candidates:
                _log.debug("PlaylistStudio: candidate pool empty at slot %d — stopping", slot)
                break

            best_path:  Optional[str]   = None
            best_score: float           = -1.0
            best_arc:   float           = 0.0
            best_trans: float           = 1.0

            last_path = playlist[-1]

            for cand_path, sim_score in candidates:
                # Diversity gate
                if not self._diversity_ok(cand_path, playlist, request):
                    continue

                # Arc score
                eng       = self._track_energy(cand_path)
                arc_score = _gaussian_score(eng, tgt, request.arc_sharpness)

                # Transition smoothness
                trans = self._cosine_pair(last_path, cand_path)
                if trans < (1.0 - request.transition_threshold):
                    trans *= 0.4   # jarring jump penalty

                combined = (
                    request.arc_weight  * arc_score
                    + request.sim_weight * sim_score * trans
                )

                if combined > best_score:
                    best_score = combined
                    best_path  = cand_path
                    best_arc   = arc_score
                    best_trans = trans

            if best_path is None:
                # All candidates failed diversity — relax and take any
                for cand_path, sim_score in candidates[:request.candidate_pool]:
                    if cand_path not in used:
                        best_path  = cand_path
                        eng        = self._track_energy(cand_path)
                        best_arc   = _gaussian_score(eng, tgt, request.arc_sharpness)
                        best_trans = self._cosine_pair(last_path, cand_path)
                        break

            if best_path is None:
                break

            playlist.append(best_path)
            used.add(best_path)
            arc_targets.append(tgt)
            arc_scores.append(best_arc)
            trans_scores.append(best_trans)

            if self._has_vec(best_path):
                n_annotated += 1
            else:
                n_fallback += 1

            # Update frontier: EMA toward the newly added track
            frontier_vec = self._ema_frontier(frontier_vec, best_path, alpha=0.30)

        result = StudioResult(
            tracks=playlist,
            arc_targets=arc_targets,
            arc_scores=arc_scores,
            transition_scores=trans_scores,
            seed_paths=seeds,
            arc_shape=request.arc_shape.value,
            n_annotated=n_annotated,
            n_fallback=n_fallback,
        )
        _log.info("PlaylistStudio.build: %s", result.summary())
        return result

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _has_vec(self, path: str) -> bool:
        ann = self._library.get_annotation(path)
        return bool(ann and ann.get("mood_vec"))

    def _track_energy(self, path: str) -> float:
        """Energy proxy in [0, 1] for arc scoring.

        Priority: spotify_energy → spotify_valence → 0.5 (neutral).
        """
        ann = self._library.get_annotation(path) or {}
        e = ann.get("spotify_energy")
        if e is not None:
            try:
                return max(0.0, min(1.0, float(e)))
            except (TypeError, ValueError):
                pass
        v = ann.get("spotify_valence")
        if v is not None:
            try:
                return max(0.0, min(1.0, float(v)))
            except (TypeError, ValueError):
                pass
        # Last resort: BPM normalised to [0, 1] over typical [60, 200] range
        bpm = ann.get("bpm")
        if bpm is None:
            meta = self._library.get_meta(path) or {}
            bpm  = meta.get("bpm")
        if bpm is not None:
            try:
                return max(0.0, min(1.0, (float(bpm) - 60.0) / 140.0))
            except (TypeError, ValueError):
                pass
        return 0.5

    def _vec(self, path: str) -> Optional[list[float]]:
        ann = self._library.get_annotation(path) or {}
        return ann.get("mood_vec")

    def _cosine_pair(self, a: str, b: str) -> float:
        va, vb = self._vec(a), self._vec(b)
        if va is None or vb is None:
            return 0.5   # neutral when not annotated
        try:
            av = np.asarray(va, dtype=np.float32)
            bv = np.asarray(vb, dtype=np.float32)
            ma = np.linalg.norm(av)
            mb = np.linalg.norm(bv)
            if ma < 1e-9 or mb < 1e-9:
                return 0.5
            return float(np.clip(np.dot(av, bv) / (ma * mb), -1.0, 1.0))
        except Exception:
            return 0.5

    def _centroid(self, paths: list[str]) -> Optional[list[float]]:
        """L2-normalised centroid of mood_vec for all annotated paths."""
        vecs = [self._vec(p) for p in paths if self._vec(p)]
        if not vecs:
            return None
        arr = np.mean([np.asarray(v, dtype=np.float32) for v in vecs], axis=0)
        n   = np.linalg.norm(arr)
        return list(arr / n) if n > 1e-9 else list(arr)

    def _ema_frontier(
        self,
        frontier: Optional[list[float]],
        new_path: str,
        alpha:    float = 0.30,
    ) -> Optional[list[float]]:
        """EMA step: frontier = (1-α) × frontier + α × new_vec, then L2-norm."""
        new_vec = self._vec(new_path)
        if new_vec is None:
            return frontier
        if frontier is None:
            return new_vec
        try:
            fv = np.asarray(frontier, dtype=np.float32)
            nv = np.asarray(new_vec, dtype=np.float32)
            ema = (1.0 - alpha) * fv + alpha * nv
            n   = np.linalg.norm(ema)
            return list(ema / n) if n > 1e-9 else list(ema)
        except Exception:
            return frontier

    def _get_candidates(
        self,
        frontier_vec: Optional[list[float]],
        used:         set[str],
        pool_size:    int,
        last_path:    Optional[str] = None,
    ) -> list[tuple[str, float]]:
        """Similarity candidates for the next slot, excluding *used* paths."""
        from phi.core.similarity import find_similar_to_vec, _bpm_radio

        if frontier_vec is not None:
            results = find_similar_to_vec(
                frontier_vec, self._library,
                n=pool_size,
                vec_key="mood_vec",
                exclude=used,
            )
            if results:
                return results

        # Fallback: BPM proximity from the last added track
        if last_path:
            bpm_list = _bpm_radio(last_path, self._library, pool_size)
            return [(p, 1.0 - i / max(len(bpm_list), 1)) for i, p in enumerate(bpm_list) if p not in used]

        return [(p, 0.5) for p in self._library.playlist if p not in used][:pool_size]

    def _diversity_ok(
        self,
        path:    str,
        playlist: list[str],
        request: StudioRequest,
    ) -> bool:
        """Return True when adding *path* respects the diversity gates."""
        meta   = self._library.get_meta(path) or {}
        ann    = self._library.get_annotation(path) or {}
        artist = (meta.get("artist") or "").strip().lower()
        genre  = (ann.get("genre") or meta.get("genre") or "").strip().lower()

        if artist:
            artist_count = sum(
                1 for p in playlist
                if ((self._library.get_meta(p) or {}).get("artist") or "").strip().lower() == artist
            )
            if artist_count >= request.max_per_artist:
                return False

        if genre:
            genre_count = sum(
                1 for p in playlist
                if (
                    (self._library.get_annotation(p) or {}).get("genre") or
                    (self._library.get_meta(p) or {}).get("genre") or ""
                ).strip().lower() == genre
            )
            if genre_count >= request.max_per_genre:
                return False

        return True


# ── Arc math (mirrors ArcEngine.target, no dependency on ArcEngine) ───────────

def _arc_target(shape: ArcShape, step: int, horizon: int) -> float:
    """Target energy in [0, 1] for the given slot and shape."""
    t = min(1.0, step / max(1, horizon - 1))
    if shape == ArcShape.FLAT:
        return 0.5
    if shape == ArcShape.RISING:
        return t
    if shape == ArcShape.FALLING:
        return 1.0 - t
    if shape == ArcShape.PEAK:
        return 4.0 * t * (1.0 - t)
    if shape == ArcShape.VALLEY:
        return 1.0 - 4.0 * t * (1.0 - t)
    if shape == ArcShape.WAVE:
        return 0.5 + 0.5 * math.sin(2.0 * math.pi * t)
    return 0.5


def _gaussian_score(energy: float, target: float, k: float) -> float:
    """Gaussian proximity score: 1.0 when energy == target, → 0 as gap grows."""
    return 1.0 / (1.0 + k * (energy - target) ** 2)
