"""Layer 10 formulas match the live phi implementations."""
from __future__ import annotations

import math

import numpy as np

from graph.topology_index import t_b_to_alpha
from phi.core.ranker._constants import HELM_FLOOR, NOVELTY_HALF_LIFE, NOVELTY_NEVER_HEARD, WEIGHTS
from phi.core.ranker._scoring import _confidence_weights, _novelty_score, ash_yield
from phi.engine.arc_scorer import ArcScorer
from phi.meta.consensus import buoyancy_score
from phi.models.dragon_curve import DragonCurve
from phi.topology.primitives import TopologicalInvariant


def test_novelty_never_heard_and_half_life():
    assert _novelty_score({}) == NOVELTY_NEVER_HEARD
    days = NOVELTY_HALF_LIFE
    expected = min(1.0, 1.0 - math.exp(-days * math.log(2) / NOVELTY_HALF_LIFE))
    from datetime import datetime, timedelta

    last = (datetime.now() - timedelta(days=days)).isoformat()
    assert _novelty_score({"last_played": last}) == round(expected, 4)


def test_ash_yield_phi_cap():
    assert ash_yield(3) == 8.0
    assert ash_yield(4) == min(32.0, 8.0 * math.exp(0.20 * 1))
    assert ash_yield(10_000) == 32.0


def test_helm_floor_blocks_elo_takeover():
    w = _confidence_weights({"buoyancy": 0.0}, dict(WEIGHTS))
    raw_genre = WEIGHTS["genre"] * HELM_FLOOR
    raw_total = (
        WEIGHTS["genre"] * HELM_FLOOR
        + WEIGHTS["mood"] * HELM_FLOOR
        + WEIGHTS["phi_rank"] * HELM_FLOOR
        + WEIGHTS["novelty"]
        + WEIGHTS["elo"]
    )
    assert abs(sum(w.values()) - 1.0) < 1e-9
    assert w["genre"] == raw_genre / raw_total


def test_buoyancy_zero_without_catalog():
    assert buoyancy_score({}, {}) == 0.0
    b = buoyancy_score(
        {
            "spotify_enriched": True,
            "mb_enriched": True,
            "lfm_enriched": True,
            "discogs_enriched": True,
            "bpm_confidence": 1.0,
            "genre_consensus": ["a", "b", "c"],
        },
        {},
    )
    assert b == 1.0 or b >= 0.75


def test_d4_a_matches_doc():
    d1 = np.array([1.0, 0.0])
    d3 = np.array([0.0, 2.0])
    d2 = 0.5
    assert DragonCurve.score_a(d1, d2, d3) == 2.0 / 1.0 - 0.5


def test_arc_continuation_perfect_and_half():
    scorer = ArcScorer(capacity=16)
    for _ in range(8):
        scorer.push(10.0)
    assert scorer.score_candidate(10.0) == 1.0
    # level=10, slope=0, delta=10 → 1/(1+1)=0.5
    assert abs(scorer.score_candidate(20.0) - 0.5) < 1e-9


def test_euler_and_t_b_alpha():
    inv = TopologicalInvariant.from_counts(V=3, E=3, T=1, beta_0=1)
    assert inv.chi == 3 - 3 + 1
    assert t_b_to_alpha(1.0) == 1.0
    assert t_b_to_alpha(-1.0) == 0.0
    assert t_b_to_alpha(0.0) == 0.5
    assert abs(inv.t_b_norm) <= 1.0


def test_t_b_formula_from_counts():
    inv = TopologicalInvariant.from_counts(V=4, E=4, T=0, beta_0=1)
    V, E, T = 4, 4, 1  # T floored to 1 inside basin_sequestration
    b0, b1 = 1, max(0, 1 - (4 - 4 + 0))
    D = V / b0
    D_M = E / V
    A_xG = V * D * math.sqrt(D_M)
    BSH = b1 - D
    Sc = float(4 - 4 + 0) * b0
    BHD = Sc - D
    expected = A_xG * abs(BSH) / T - abs(BHD - 1.0)
    assert inv.t_b == expected
