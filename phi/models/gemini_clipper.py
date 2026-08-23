"""
GeminiClipper — Stage III execution engine for the phi model.

Architecture (keep/2025-12-06-114407-gemini-clipper):

    query
      │
      ├─► Semantic scoring  (TF-IDF over track text)          sem ∈ [0,1]^N
      │
      └─► H-space proximity (query encoded → cosine on H)     h_space ∈ [0,1]^N
              │
              ▼
          P_sps = (1−α)·sem + α·h_space
              │
              ▼
          top-K ClippedTrack  ranked by P_sps
              │
              ▼
          ClipResult.context  — compact metadata blocks ready for LLM synthesis

Query → H-space path:
    Parse query tokens → pseudo-lfm_tags on a dummy Track
    MetadataEncoder.encode_one() → (512,)
    CLAPProjection.forward() → (1, 256) L2-norm → squeeze
    Cosine similarity against snap.H (already L2-normalised → plain dot product)
    Map [-1, 1] → [0, 1]

Semantic path:
    Build TF-IDF corpus from each track's text (name + artist + album + tags).
    Cosine similarity of query TF-IDF vector against corpus matrix.
    Both implemented in psspps.scorer (imported; no duplication).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from phi._track import Track
from phi.graph._snapshot import PhiGraphSnapshot
from phi.models._metadata_encoder import MetadataEncoder
from phi.models.clap_proj import CLAPProjection
from psspps.scorer import (
    build_tfidf,
    query_vector,
    semantic_scores,
)

__all__ = [
    "GeminiClipper",
    "ClippedTrack",
    "ClipResult",
]


# ---------------------------------------------------------------------------
# Track text representation
# ---------------------------------------------------------------------------


def _track_text(track: Track) -> str:
    """Flatten a Track's human-readable fields into one plain-text document."""
    parts: list[str] = [track.name, track.artist, track.album, track.itunes_genre]
    parts += track.lfm_tags
    parts += track.discogs_genre
    parts += track.discogs_style
    return " ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Query → H-space embedding
# ---------------------------------------------------------------------------


def _query_h_vec(
    query: str,
    encoder: MetadataEncoder,
    proj: CLAPProjection,
) -> np.ndarray:
    """
    Embed a free-text query into H-space (256-d, L2-normalised).

    Tokens from the query string become pseudo-lfm_tags on a dummy Track,
    which the MetadataEncoder converts to a (512,) feature vector.
    CLAPProjection projects that to the L2-normalised (256,) H-space.

    Parameters
    ----------
    query   : raw query string
    encoder : MetadataEncoder with vocab already set (from PhiGraph.build)
    proj    : CLAPProjection (same instance used to build snap.H)

    Returns
    -------
    h : (256,) float64, L2-normalised
    """
    tokens = re.findall(r"[a-z0-9]+", query.lower())
    dummy = Track(
        path=Path("/__query__"),
        json_path=Path("/__query__.json"),
        lfm_tags=tokens,
    )
    x = encoder.encode_one(dummy)           # (512,)
    h = proj.forward(x[np.newaxis, :])      # (1, 256)
    return h[0]                             # (256,) already L2-normalised


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


def _format_duration(duration_s: float) -> str:
    mins, secs = divmod(max(0, int(duration_s)), 60)
    return f"{mins}:{secs:02d}"


def _format_context_block(rank: int, track: Track, p_sps: float) -> str:
    tags = ", ".join(track.all_tags[:8]) or "—"
    lines = [
        f"[{rank + 1}] {track.display_name}  (P_sps={p_sps:.4f})",
        f"    Tags: {tags}",
    ]
    album_parts = [p for p in [track.album, f"({track.year})" if track.year else ""] if p]
    if album_parts:
        lines.append(f"    Album: {' '.join(album_parts)}")
    key_str = track.key
    if track.key_camelot:
        key_str = f"{key_str} / {track.key_camelot}" if key_str else track.key_camelot
    meta = []
    if key_str:
        meta.append(f"Key: {key_str}")
    if track.duration_s > 0:
        meta.append(f"Duration: {_format_duration(track.duration_s)}")
    if meta:
        lines.append(f"    {' | '.join(meta)}")
    return "\n".join(lines)


@dataclass
class ClippedTrack:
    """One track selected by the clipper with its scoring breakdown."""
    track: Track
    rank: int               # 0-based; 0 = highest P_sps
    semantic_score: float
    h_space_score: float
    p_sps: float
    context_block: str      # pre-formatted metadata text block


@dataclass
class ClipResult:
    """
    Result of GeminiClipper.clip().

    context : assembled multi-track metadata string ready for LLM synthesis.
    """
    query: str
    top_k: list[ClippedTrack]
    context: str
    n_tracks_searched: int
    alpha: float


# ---------------------------------------------------------------------------
# GeminiClipper
# ---------------------------------------------------------------------------


class GeminiClipper:
    """
    Clips the top-K most relevant tracks from a PhiGraphSnapshot for a query.

    blend_score = (1−α)·semantic + α·h_space

    Parameters
    ----------
    proj    : CLAPProjection — the same instance that built snap.H
    encoder : MetadataEncoder — with vocab set (call PhiGraph.build first)
    top_k   : number of tracks to return (default 5)
    alpha   : blend weight — 0.0 = pure TF-IDF, 1.0 = pure H-space (default 0.5)

    Queue mastering
    ---------------
    TF-IDF corpus matrix is rebuilt once per unique snapshot (keyed by id(snap)).
    Subsequent clip() calls on the same snapshot reuse the cached matrix — O(1)
    corpus lookup instead of O(N×V) rebuild on every query.
    A new snapshot (after build/refresh) automatically invalidates the cache.
    """

    def __init__(
        self,
        proj: CLAPProjection,
        encoder: MetadataEncoder,
        top_k: int = 5,
        alpha: float = 0.5,
    ) -> None:
        self.proj = proj
        self.encoder = encoder
        self.top_k = top_k
        self.alpha = float(np.clip(alpha, 0.0, 1.0))
        # Snapshot-keyed TF-IDF cache: id(snap) → (tfidf_matrix, vocab)
        # Holds at most one entry — cleared when snap changes.
        self._tfidf_snap_id: int = -1
        self._tfidf_matrix: Optional[np.ndarray] = None
        self._tfidf_vocab: Optional[list[str]] = None

    def clip(
        self,
        query: str,
        snap: PhiGraphSnapshot,
    ) -> ClipResult:
        """
        Score every track in snap against the query and return top-K.

        Parameters
        ----------
        query : free-text search string
        snap  : current PhiGraphSnapshot (must be already built)

        Returns
        -------
        ClipResult
        """
        tracks = snap.tracks
        N = snap.N

        # ---- 1. Semantic (TF-IDF) — snapshot-keyed cache -------------------
        snap_id = id(snap)
        if snap_id != self._tfidf_snap_id:
            corpus = [_track_text(t) for t in tracks]
            self._tfidf_matrix, self._tfidf_vocab = build_tfidf(corpus)
            self._tfidf_snap_id = snap_id
        tfidf_matrix = self._tfidf_matrix
        vocab        = self._tfidf_vocab
        q_vec = query_vector(query, vocab)
        sem = semantic_scores(q_vec, tfidf_matrix)          # (N,)

        # ---- 2. H-space proximity ------------------------------------------
        # snap.H is already L2-normalised → cosine sim = dot product
        q_h = _query_h_vec(query, self.encoder, self.proj)  # (256,) L2-norm
        raw_cos = snap.H @ q_h                              # (N,) ∈ [-1, 1]
        h_scores = np.clip((raw_cos + 1.0) / 2.0, 0.0, 1.0)  # → [0, 1]

        # ---- 3. Blend score ------------------------------------------------
        blend_score = (1.0 - self.alpha) * sem + self.alpha * h_scores  # (N,)

        # ---- 4. Rank and clip ----------------------------------------------
        k = min(self.top_k, N)
        ranked_idx = np.argsort(blend_score)[::-1][:k]

        clipped: list[ClippedTrack] = []
        for rank, idx in enumerate(ranked_idx):
            track = tracks[idx]
            score = float(blend_score[idx])
            block = _format_context_block(rank, track, score)
            clipped.append(ClippedTrack(
                track=track,
                rank=rank,
                semantic_score=round(float(sem[idx]), 4),
                h_space_score=round(float(h_scores[idx]), 4),
                p_sps=round(score, 4),
                context_block=block,
            ))

        header = f"Query: {query}\n{'-' * 60}"
        context = header + "\n" + "\n\n".join(ct.context_block for ct in clipped)

        return ClipResult(
            query=query,
            top_k=clipped,
            context=context,
            n_tracks_searched=N,
            alpha=self.alpha,
        )

    def __repr__(self) -> str:
        return (
            f"<GeminiClipper top_k={self.top_k} alpha={self.alpha}>"
        )
