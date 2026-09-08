"""
Tests for graph.edge_scorer — EdgeScore, EdgeScorer, and linker integration.
"""
from __future__ import annotations

import math
from typing import Any
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from graph.edge_scorer import (
    EdgeScore,
    EdgeScorer,
    SCORER,
    EDGE_FORMULA_IDS,
    _fallback_cosine,
    _fallback_jaccard,
    validate_edge_formulas,
)


# ---------------------------------------------------------------------------
# Fallback math (used when registry unavailable)
# ---------------------------------------------------------------------------

class TestFallbacks:
    def test_cosine_identical(self):
        a = [1.0, 0.0, 0.0]
        assert abs(_fallback_cosine(a, a) - 1.0) < 1e-9

    def test_cosine_orthogonal(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(_fallback_cosine(a, b)) < 1e-9

    def test_cosine_zero_vector(self):
        assert _fallback_cosine([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_jaccard_identical(self):
        assert abs(_fallback_jaccard(["a", "b"], ["a", "b"]) - 1.0) < 1e-9

    def test_jaccard_disjoint(self):
        assert _fallback_jaccard(["a"], ["b"]) == 0.0

    def test_jaccard_partial(self):
        result = _fallback_jaccard(["a", "b"], ["b", "c"])
        assert abs(result - 1/3) < 1e-9

    def test_jaccard_empty(self):
        assert _fallback_jaccard([], []) == 0.0


# ---------------------------------------------------------------------------
# EdgeScore dataclass
# ---------------------------------------------------------------------------

class TestEdgeScore:
    def _make(self, cos=0.8, jac=0.5, ew=0.9, rp=0.7, pc=0.2) -> EdgeScore:
        return EdgeScore(
            stem_a="a", stem_b="b",
            cosine_sim=cos, jaccard=jac, edge_weight=ew,
            rag_priority=rp, path_cost=pc,
            formula_trace={}, fallback_used=False,
        )

    def test_composite_blend(self):
        e = self._make(cos=1.0, jac=1.0)
        assert abs(e.composite - 1.0) < 1e-9

    def test_composite_clipped(self):
        e = self._make(cos=2.0, jac=2.0)
        assert e.composite <= 1.0

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        for key in ("stem_a", "stem_b", "cosine_sim", "jaccard", "edge_weight",
                    "rag_priority", "path_cost", "composite", "formula_trace",
                    "fallback_used"):
            assert key in d


# ---------------------------------------------------------------------------
# EdgeScorer — individual formula calls
# ---------------------------------------------------------------------------

class TestEdgeScorerFormulas:
    def test_cosine_sim_via_registry(self):
        scorer = EdgeScorer()
        a = [1.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        cos, fallback = scorer.cosine_sim(a, b)
        # Either registry or fallback: identical vectors → cos ≈ 1.0
        assert abs(cos - 1.0) < 1e-6

    def test_cosine_sim_orthogonal(self):
        scorer = EdgeScorer()
        cos, _ = scorer.cosine_sim([1.0, 0.0], [0.0, 1.0])
        assert abs(cos) < 1e-6

    def test_cosine_sim_numpy_arrays(self):
        scorer = EdgeScorer()
        a = np.array([0.6, 0.8])
        b = np.array([0.6, 0.8])
        cos, _ = scorer.cosine_sim(a, b)
        assert abs(cos - 1.0) < 1e-6

    def test_jaccard_full_overlap(self):
        scorer = EdgeScorer()
        jac, _ = scorer.jaccard_affinity(["math", "code"], ["math", "code"])
        assert abs(jac - 1.0) < 1e-6

    def test_jaccard_no_overlap(self):
        scorer = EdgeScorer()
        jac, _ = scorer.jaccard_affinity(["math"], ["code"])
        assert abs(jac) < 1e-6

    def test_jaccard_partial(self):
        scorer = EdgeScorer()
        jac, _ = scorer.jaccard_affinity(["a", "b"], ["b", "c"])
        assert abs(jac - 1/3) < 1e-3

    def test_edge_weight_single_facet(self):
        scorer = EdgeScorer()
        ew, _ = scorer.edge_weight([0.8], [1.0])
        # F_EDGE_WEIGHT: sum(sim * reinforcement) = 0.8 * 1.0 = 0.8
        assert abs(ew - 0.8) < 1e-6

    def test_edge_weight_multi_facet(self):
        scorer = EdgeScorer()
        ew, _ = scorer.edge_weight([0.5, 0.5], [1.0, 0.0])
        # sum([0.5*1.0, 0.5*0.0]) = 0.5
        assert abs(ew - 0.5) < 1e-6

    def test_rag_priority_basic(self):
        scorer = EdgeScorer()
        rp, _ = scorer.rag_priority(X_norm=0.8, T_pos=0.2, O_N=1.0, P_risk=1.0)
        # F_RAG_PRIORITY: (0.8/1.0) - (0.2/1.0) = 0.6
        assert abs(rp - 0.6) < 1e-6

    def test_rag_priority_zero_penalty(self):
        scorer = EdgeScorer()
        rp, _ = scorer.rag_priority(X_norm=0.9, T_pos=0.0)
        assert abs(rp - 0.9) < 1e-6

    def test_path_cost_one_hop(self):
        scorer = EdgeScorer()
        pc, _ = scorer.path_cost(sim=0.8, hop_count=1)
        # F_PATH_COST: 1 * (1 - 0.8) = 0.2
        assert abs(pc - 0.2) < 1e-6

    def test_path_cost_two_hops(self):
        scorer = EdgeScorer()
        pc, _ = scorer.path_cost(sim=0.5, hop_count=2)
        # 2 * (1 - 0.5) = 1.0
        assert abs(pc - 1.0) < 1e-6

    def test_path_cost_perfect_sim(self):
        scorer = EdgeScorer()
        pc, _ = scorer.path_cost(sim=1.0, hop_count=5)
        assert abs(pc) < 1e-9

    def test_local_coherence_uniform(self):
        scorer = EdgeScorer()
        coh, _ = scorer.local_coherence([1.0, 1.0], [0.5, 0.5], [1.0, 1.0])
        assert abs(coh - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# EdgeScorer.score_pair
# ---------------------------------------------------------------------------

class TestEdgeScorerScorePair:
    def _vecs(self):
        return (
            np.array([1.0, 0.0, 0.0]),
            np.array([1.0, 0.0, 0.0]),
        )

    def test_identical_nodes(self):
        scorer = EdgeScorer()
        va, vb = self._vecs()
        edge = scorer.score_pair("a", "b", va, vb, ["tag1"], ["tag1"])
        assert edge.stem_a == "a"
        assert edge.stem_b == "b"
        assert edge.cosine_sim == pytest.approx(1.0, abs=1e-5)
        assert edge.jaccard    == pytest.approx(1.0, abs=1e-5)

    def test_orthogonal_vecs(self):
        scorer = EdgeScorer()
        va = np.array([1.0, 0.0])
        vb = np.array([0.0, 1.0])
        edge = scorer.score_pair("a", "b", va, vb)
        assert edge.cosine_sim == pytest.approx(0.0, abs=1e-5)

    def test_formula_trace_present(self):
        scorer = EdgeScorer()
        va, vb = np.array([0.6, 0.8]), np.array([0.6, 0.8])
        edge = scorer.score_pair("x", "y", va, vb)
        assert "F_COSINE_SIMILARITY" in edge.formula_trace
        assert "F_JACCARD_AFFINITY"  in edge.formula_trace
        assert "F_EDGE_WEIGHT"       in edge.formula_trace
        assert "F_RAG_PRIORITY"      in edge.formula_trace
        assert "F_PATH_COST"         in edge.formula_trace

    def test_to_dict_ok(self):
        scorer = EdgeScorer()
        va, vb = self._vecs()
        d = scorer.score_pair("a", "b", va, vb).to_dict()
        assert isinstance(d["cosine_sim"], float)
        assert isinstance(d["formula_trace"], dict)

    def test_hop_count_affects_path_cost(self):
        scorer = EdgeScorer()
        va = np.array([0.6, 0.8])
        vb = np.array([0.0, 0.0])  # zero vec → cosine 0
        e1 = scorer.score_pair("a", "b", va, va, hop_count=1)
        e2 = scorer.score_pair("a", "b", va, va, hop_count=2)
        # Both identical vecs → cosine=1 → path_cost = hop * 0 = 0
        assert e2.path_cost >= e1.path_cost


# ---------------------------------------------------------------------------
# EdgeScorer.score_corpus
# ---------------------------------------------------------------------------

class TestEdgeScorerScoreCorpus:
    def _make_corpus(self, n: int = 5):
        np.random.seed(42)
        vecs = np.random.randn(n, 4)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        vecs /= np.where(norms > 1e-12, norms, 1.0)
        stems = [f"node_{i}" for i in range(n)]
        tags  = [["tag"] for _ in range(n)]
        return vecs, stems, tags

    def test_excludes_target_stem(self):
        scorer = EdgeScorer()
        vecs, stems, tags = self._make_corpus()
        results = scorer.score_corpus(
            "node_0", vecs[0], ["tag"],
            stems, vecs, tags,
            threshold=0.0,
        )
        assert all(stem != "node_0" for _, stem, _ in results)

    def test_threshold_filters(self):
        scorer = EdgeScorer()
        vecs, stems, tags = self._make_corpus(5)
        # High threshold → few or no results
        results = scorer.score_corpus(
            "node_0", vecs[0], [],
            stems, vecs, tags,
            threshold=2.0,  # impossible threshold
        )
        assert results == []

    def test_top_k_limits(self):
        scorer = EdgeScorer()
        vecs, stems, tags = self._make_corpus(10)
        results = scorer.score_corpus(
            "node_0", vecs[0], [],
            stems, vecs, tags,
            threshold=0.0,
            top_k=3,
        )
        assert len(results) <= 3

    def test_sorted_by_rag_priority(self):
        scorer = EdgeScorer()
        vecs, stems, tags = self._make_corpus(6)
        results = scorer.score_corpus(
            "node_0", vecs[0], [],
            stems, vecs, tags,
            threshold=0.0,
        )
        priorities = [r[0] for r in results]
        assert priorities == sorted(priorities, reverse=True)

    def test_returns_edge_scores(self):
        scorer = EdgeScorer()
        vecs, stems, tags = self._make_corpus(4)
        results = scorer.score_corpus(
            "node_0", vecs[0], [],
            stems, vecs, tags,
            threshold=0.0,
        )
        for rp, stem, edge in results:
            assert isinstance(edge, EdgeScore)
            assert edge.stem_a == "node_0"
            assert "F_COSINE_SIMILARITY" in edge.formula_trace


# ---------------------------------------------------------------------------
# Strict mode enforcement
# ---------------------------------------------------------------------------

class TestStrictMode:
    def test_strict_true_raises_on_missing_formula(self):
        """strict=True must raise FormulaNotReady when a formula is absent."""
        from workers.formula_registry import FormulaNotReady

        def bad_call(formula_id, **kwargs):
            raise FormulaNotReady(f"{formula_id} not ready")

        scorer = EdgeScorer(strict=True)
        # Patch _call to simulate a missing formula at eval time
        with patch.object(scorer, "_call", side_effect=bad_call):
            with pytest.raises(FormulaNotReady):
                scorer.cosine_sim([1.0, 0.0], [1.0, 0.0])

    def test_strict_false_uses_fallback(self):
        """strict=False falls back to Python math when formula fails."""
        from workers.formula_registry import FormulaNotReady

        def bad_call(formula_id, **kwargs):
            raise FormulaNotReady(f"{formula_id} not ready")

        scorer = EdgeScorer(strict=False)
        with patch.object(scorer, "_call", side_effect=bad_call):
            cos, fallback = scorer.cosine_sim([1.0, 0.0], [1.0, 0.0])
        assert abs(cos - 1.0) < 1e-6
        assert fallback is True

    def test_strict_false_jaccard_fallback(self):
        from workers.formula_registry import FormulaNotReady
        scorer = EdgeScorer(strict=False)
        with patch.object(scorer, "_call", side_effect=FormulaNotReady("x")):
            jac, fallback = scorer.jaccard_affinity(["a"], ["a"])
        assert abs(jac - 1.0) < 1e-6
        assert fallback is True

    def test_strict_false_rag_priority_fallback(self):
        from workers.formula_registry import FormulaNotReady
        scorer = EdgeScorer(strict=False)
        with patch.object(scorer, "_call", side_effect=FormulaNotReady("x")):
            rp, fallback = scorer.rag_priority(X_norm=0.7, T_pos=0.1)
        assert abs(rp - 0.6) < 1e-6
        assert fallback is True

    def test_strict_false_path_cost_fallback(self):
        from workers.formula_registry import FormulaNotReady
        scorer = EdgeScorer(strict=False)
        with patch.object(scorer, "_call", side_effect=FormulaNotReady("x")):
            pc, fallback = scorer.path_cost(sim=0.8, hop_count=1)
        assert abs(pc - 0.2) < 1e-6
        assert fallback is True

    def test_default_is_strict(self):
        """The default EdgeScorer() constructor is strict=True."""
        scorer = EdgeScorer()
        assert scorer._strict is True

    def test_SCORER_singleton_is_strict(self):
        """Module-level SCORER is strict — not a soft dependency."""
        assert SCORER._strict is True


# ---------------------------------------------------------------------------
# validate_edge_formulas
# ---------------------------------------------------------------------------

class TestValidateEdgeFormulas:
    def test_all_required_formulas_ready(self):
        """validate_edge_formulas() must pass with the real registry."""
        report = validate_edge_formulas()
        for fid in EDGE_FORMULA_IDS:
            assert fid in report
            assert report[fid] == "ready", f"{fid} is not ready: {report[fid]}"

    def test_raises_when_formula_missing(self):
        from workers.formula_registry import FormulaNotReady

        # Patch REGISTRY.__contains__ to pretend a formula is missing
        with patch("graph.edge_scorer._registry") as mock_reg:
            mock_spec = MagicMock()
            mock_spec.status = "unimplemented"
            mock_instance = MagicMock()
            mock_instance.__contains__ = MagicMock(return_value=False)
            mock_reg.return_value = mock_instance

            # validate_edge_formulas imports REGISTRY directly, so patch that
            from workers import formula_registry as fr_mod
            original = fr_mod.REGISTRY

            class _FakeReg:
                def __contains__(self, fid):
                    return False
                def inspect(self, fid):
                    return {"status": "missing"}

            fr_mod.REGISTRY = _FakeReg()
            try:
                with pytest.raises(FormulaNotReady):
                    validate_edge_formulas()
            finally:
                fr_mod.REGISTRY = original

    def test_edge_formula_ids_covers_six(self):
        assert len(EDGE_FORMULA_IDS) == 6
        assert "F_COSINE_SIMILARITY" in EDGE_FORMULA_IDS
        assert "F_RAG_PRIORITY"      in EDGE_FORMULA_IDS
        assert "F_PATH_COST"         in EDGE_FORMULA_IDS


# ---------------------------------------------------------------------------
# Registry fallback (when registry unavailable) — strict=False only
# ---------------------------------------------------------------------------

class TestRegistryFallback:
    def test_cosine_fallback_non_strict(self):
        from workers.formula_registry import FormulaNotReady
        scorer = EdgeScorer(strict=False)
        with patch.object(scorer, "_call", side_effect=FormulaNotReady("x")):
            cos, fallback = scorer.cosine_sim([1.0, 0.0], [1.0, 0.0])
        assert abs(cos - 1.0) < 1e-6
        assert fallback is True

    def test_jaccard_fallback_non_strict(self):
        from workers.formula_registry import FormulaNotReady
        scorer = EdgeScorer(strict=False)
        with patch.object(scorer, "_call", side_effect=FormulaNotReady("x")):
            jac, fallback = scorer.jaccard_affinity(["a"], ["a"])
        assert abs(jac - 1.0) < 1e-6
        assert fallback is True

    def test_rag_priority_fallback_non_strict(self):
        from workers.formula_registry import FormulaNotReady
        scorer = EdgeScorer(strict=False)
        with patch.object(scorer, "_call", side_effect=FormulaNotReady("x")):
            rp, fallback = scorer.rag_priority(X_norm=0.7, T_pos=0.1)
        assert abs(rp - 0.6) < 1e-6
        assert fallback is True


# ---------------------------------------------------------------------------
# SCORER singleton
# ---------------------------------------------------------------------------

class TestScorerSingleton:
    def test_singleton_works(self):
        cos, _ = SCORER.cosine_sim([1.0, 0.0], [1.0, 0.0])
        assert abs(cos - 1.0) < 1e-6

    def test_singleton_has_defaults(self):
        assert SCORER._rag_O_N    == 1.0
        assert SCORER._rag_P_risk == 1.0
        assert SCORER._edge_hop   == 1
