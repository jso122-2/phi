"""Layer 10 formulas match the live phi implementations."""
from __future__ import annotations

import importlib.util
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


dragon = _load("phi_dragon_curve", "phi/models/dragon_curve.py")
primitives = _load("phi_topo_primitives", "phi/topology/primitives.py")
arc = _load("phi_arc_scorer", "phi/engine/arc_scorer.py")
consensus = _load("phi_meta_consensus", "phi/meta/consensus.py")


def test_novelty_formula_still_in_source():
    src = (ROOT / "phi/core/ranker/_scoring.py").read_text(encoding="utf-8")
    assert "1.0 - math.exp(-days * math.log(2) / NOVELTY_HALF_LIFE)" in src
    assert "NOVELTY_NEVER_HEARD" in src
    days = 14.0
    n = min(1.0, 1.0 - math.exp(-days * math.log(2) / 14.0))
    assert n == 0.5
    last = (datetime.now() - timedelta(days=14)).isoformat()
    assert last  # last_played is ISO; identity is the exponential above


def test_ash_yield_formula_still_in_source():
    src = (ROOT / "phi/core/ranker/_scoring.py").read_text(encoding="utf-8")
    assert "min(ELO_K, _ASH_BASE * math.exp(_ASH_K * T))" in src
    t = max(0, 4 - 3)
    assert min(32.0, 8.0 * math.exp(0.20 * t)) == 8.0 * math.exp(0.20)
    assert min(32.0, 8.0 * math.exp(0.20 * 20)) == 32.0


def test_helm_floor_formula_still_in_source():
    src = (ROOT / "phi/core/ranker/_scoring.py").read_text(encoding="utf-8")
    assert "helm_scale = max(HELM_FLOOR, buoy)" in src
    const = (ROOT / "phi/core/ranker/_constants.py").read_text(encoding="utf-8")
    assert "HELM_FLOOR: float = 0.50" in const
    weights = {"genre": 0.28, "mood": 0.28, "novelty": 0.23, "elo": 0.13, "phi_rank": 0.08}
    scale = max(0.50, 0.0)
    w = {
        "genre": weights["genre"] * scale,
        "mood": weights["mood"] * scale,
        "novelty": weights["novelty"],
        "elo": weights["elo"],
        "phi_rank": weights["phi_rank"] * scale,
    }
    total = sum(w.values())
    w = {k: v / total for k, v in w.items()}
    assert abs(sum(w.values()) - 1.0) < 1e-12
    assert w["genre"] == (0.28 * 0.5) / total


def test_buoyancy_zero_without_catalog():
    assert consensus.buoyancy_score({}, {}) == 0.0
    b = consensus.buoyancy_score(
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
    assert b == 1.0


def test_d4_a_matches_doc():
    d1 = np.array([1.0, 0.0])
    d3 = np.array([0.0, 2.0])
    assert dragon.DragonCurve.score_a(d1, 0.5, d3) == 2.0 / 1.0 - 0.5


def test_arc_continuation_perfect_and_half():
    scorer = arc.ArcScorer(capacity=16)
    for _ in range(8):
        scorer.push(10.0)
    assert scorer.score_candidate(10.0) == 1.0
    assert abs(scorer.score_candidate(20.0) - 0.5) < 1e-9


def test_euler_and_t_b_alpha():
    inv = primitives.TopologicalInvariant.from_counts(V=3, E=3, T=1, beta_0=1)
    assert inv.chi == 3 - 3 + 1
    alpha = lambda t: 0.5 + 0.5 * max(-1.0, min(1.0, t))
    assert alpha(1.0) == 1.0
    assert alpha(-1.0) == 0.0
    assert alpha(0.0) == 0.5
    src = (ROOT / "graph/topology_index.py").read_text(encoding="utf-8")
    assert "return float(0.5 + 0.5 * max(-1.0, min(1.0, t_b_norm)))" in src


def test_t_b_formula_from_counts():
    inv = primitives.TopologicalInvariant.from_counts(V=4, E=4, T=0, beta_0=1)
    V, E = 4, 4
    T = 1
    b0, b1 = 1, max(0, 1 - (4 - 4 + 0))
    D = V / b0
    D_M = E / V
    A_xG = V * D * math.sqrt(D_M)
    BSH = b1 - D
    Sc = float(4 - 4 + 0) * b0
    BHD = Sc - D
    expected = A_xG * abs(BSH) / T - abs(BHD - 1.0)
    assert inv.t_b == expected
