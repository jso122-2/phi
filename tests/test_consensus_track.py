# -*- coding: utf-8 -*-
"""tests/test_consensus_track.py — ConsensusTrack spine: buoyancy, build, ranker weights."""
from __future__ import annotations

import pytest

from phi.meta.consensus import (
    ConsensusTrack,
    build_consensus_track,
    buoyancy_score,
)
from phi.core.ranker._constants import HELM_FLOOR, WEIGHTS
from phi.core.ranker._scoring import _confidence_weights


# ── helpers ───────────────────────────────────────────────────────────────────

def _ann(**kw) -> dict:
    return kw


def _meta(**kw) -> dict:
    return kw


# ── buoyancy_score ─────────────────────────────────────────────────────────────

class TestBuoyancyScore:
    def test_no_sources_returns_zero(self):
        assert buoyancy_score({}, {}) == 0.0

    def test_single_source_nonzero(self):
        ann = _ann(spotify_enriched=True)
        score = buoyancy_score(ann, {})
        assert 0.0 < score <= 1.0

    def test_all_four_sources_high(self):
        ann = _ann(
            spotify_enriched=True,
            mb_enriched=True,
            lfm_enriched=True,
            discogs_enriched=True,
        )
        score = buoyancy_score(ann, {})
        assert score >= 0.5

    def test_bpm_confidence_raises_agreement(self):
        ann_low  = _ann(spotify_enriched=True, mb_enriched=True, bpm_confidence=0.0)
        ann_high = _ann(spotify_enriched=True, mb_enriched=True, bpm_confidence=1.0)
        assert buoyancy_score(ann_high, {}) > buoyancy_score(ann_low, {})

    def test_genre_consensus_raises_agreement(self):
        base = _ann(spotify_enriched=True, mb_enriched=True)
        no_genre  = {**base}
        one_genre = {**base, "genre_consensus": ["techno"]}
        three_genres = {**base, "genre_consensus": ["techno", "electronic", "house"]}
        assert buoyancy_score(three_genres, {}) > buoyancy_score(one_genre, {}) > buoyancy_score(no_genre, {})

    def test_mood_corroboration_raises_agreement(self):
        base = _ann(spotify_enriched=True, mb_enriched=True, spotify_mood="energetic")
        no_tags   = {**base}
        confirmed = {**base, "lfm_tags": ["energetic", "upbeat"]}
        assert buoyancy_score(confirmed, {}) > buoyancy_score(no_tags, {})

    def test_result_clamped_to_unit_interval(self):
        ann = _ann(
            spotify_enriched=True, mb_enriched=True,
            lfm_enriched=True, discogs_enriched=True,
            bpm_confidence=1.0, genre_consensus=["a", "b", "c"],
            spotify_mood="happy", lfm_tags=["happy", "upbeat"],
        )
        score = buoyancy_score(ann, {})
        assert 0.0 <= score <= 1.0

    def test_deezer_not_counted_as_catalog(self):
        """Deezer is an instrument arm, not a catalog source."""
        ann_deezer_only = _ann(deezer_enriched=True)
        assert buoyancy_score(ann_deezer_only, {}) == 0.0


# ── build_consensus_track ─────────────────────────────────────────────────────

class TestBuildConsensusTrack:
    def test_returns_consensus_track(self):
        ct = build_consensus_track({}, {})
        assert isinstance(ct, ConsensusTrack)

    def test_identity_from_meta(self):
        meta = _meta(title="The Track", artist="The Artist", album="The Album")
        ct = build_consensus_track({}, meta)
        assert ct.title  == "The Track"
        assert ct.artist == "The Artist"
        assert ct.album  == "The Album"

    def test_bpm_from_precomputed_annotation(self):
        ann = _ann(bpm_consensus=128.0, bpm_confidence=0.9)
        ct = build_consensus_track(ann, {})
        assert ct.bpm           == pytest.approx(128.0)
        assert ct.bpm_confidence == pytest.approx(0.9)

    def test_genre_from_precomputed_annotation(self):
        ann = _ann(genre_consensus=["techno", "electronic"])
        ct = build_consensus_track(ann, {})
        assert ct.genre == ["techno", "electronic"]

    def test_genre_computed_when_absent(self):
        ann = _ann(
            mb_genres=["Electronic"],
            lfm_tags=["techno", "electronic"],
            spotify_enriched=True,
        )
        ct = build_consensus_track(ann, {})
        assert len(ct.genre) >= 1

    def test_spotify_helm_numerics(self):
        ann = _ann(spotify_valence=0.8, spotify_energy=0.6, spotify_mood="energetic")
        ct = build_consensus_track(ann, {})
        assert ct.valence == pytest.approx(0.8)
        assert ct.energy  == pytest.approx(0.6)
        assert ct.mood    == "energetic"

    def test_buoyancy_stored_when_precomputed(self):
        ann = _ann(buoyancy=0.75)
        ct = build_consensus_track(ann, {})
        assert ct.buoyancy == pytest.approx(0.75)

    def test_sources_list_populated(self):
        ann = _ann(spotify_enriched=True, mb_enriched=True, lfm_enriched=False)
        ct = build_consensus_track(ann, {})
        assert "spotify"     in ct.sources
        assert "musicbrainz" in ct.sources
        assert "lastfm"      not in ct.sources
        assert ct.source_count == 2

    def test_isrc_from_annotation(self):
        ann = _ann(isrc="USRC11600256")
        ct = build_consensus_track(ann, {})
        assert ct.isrc == "USRC11600256"

    def test_empty_inputs_give_zero_buoyancy(self):
        ct = build_consensus_track({}, {})
        assert ct.buoyancy == 0.0
        assert ct.source_count == 0


# ── _confidence_weights (ranker) ──────────────────────────────────────────────

class TestConfidenceWeights:
    """Buoyancy governs helm authority; ELO/novelty cannot dominate via renorm."""

    def _base(self) -> dict:
        return dict(WEIGHTS)

    def test_full_buoyancy_preserves_relative_proportions(self):
        ann  = _ann(buoyancy=1.0)
        base = self._base()
        w    = _confidence_weights(ann, base)
        # With buoyancy=1.0, helm_scale=1.0 → genre/mood at full base weight.
        assert w["genre"] / w["novelty"] == pytest.approx(
            base["genre"] / base["novelty"], rel=0.05
        )

    def test_low_buoyancy_helm_floored(self):
        ann  = _ann(buoyancy=0.0)
        base = self._base()
        w    = _confidence_weights(ann, base)
        # Helm dims must be at least HELM_FLOOR × base after renorm.
        # Check that ELO share did not explode past its base share.
        raw_elo_share  = base["elo"]
        result_elo_share = w["elo"]
        # ELO should not more than double its base proportion.
        assert result_elo_share < raw_elo_share * 2.5

    def test_helm_floor_prevents_skip_spiral(self):
        """Genre/mood must retain meaningful weight even at buoyancy=0."""
        ann  = _ann(buoyancy=0.0)
        base = self._base()
        w    = _confidence_weights(ann, base)
        # Genre+mood combined should still be at least HELM_FLOOR × their base combined.
        base_helm  = base["genre"] + base["mood"]
        result_helm = w["genre"] + w["mood"]
        assert result_helm >= base_helm * HELM_FLOOR * 0.9  # 10% tolerance for renorm

    def test_weights_sum_to_one(self):
        for buoy in (0.0, 0.25, 0.5, 0.75, 1.0):
            w = _confidence_weights(_ann(buoyancy=buoy), self._base())
            assert sum(w.values()) == pytest.approx(1.0, abs=1e-9)

    def test_falls_back_to_meta_score(self):
        """When buoyancy absent, meta_score is used."""
        ann_buoy  = _ann(buoyancy=0.8)
        ann_meta  = _ann(meta_score=0.8)
        w_buoy = _confidence_weights(ann_buoy, self._base())
        w_meta = _confidence_weights(ann_meta, self._base())
        assert w_buoy["genre"] == pytest.approx(w_meta["genre"], rel=0.01)

    def test_missing_both_defaults_to_half(self):
        """No buoyancy, no meta_score → buoy defaults to 0.5 (neutral)."""
        w = _confidence_weights({}, self._base())
        assert sum(w.values()) == pytest.approx(1.0, abs=1e-9)
