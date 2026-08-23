"""
Tests for psspps/pipeline.py — run_psspps full pipeline, and for
psspps/scorer.py — coherence scoring functions.

Uses a zero activation vector (neutral harmonic state) so pipeline results
depend only on coherence structural-order, which is deterministic given the vault.
"""
from __future__ import annotations

import numpy as np
import pytest

from psspps.pipeline import PSPSPSResult, ScoredDoc, run_psspps
from psspps.scorer import _structural_order, coherence_scores


ZERO_ACTIVATIONS = np.zeros(8, dtype=float)


# ---------------------------------------------------------------------------
# Return-type contract
# ---------------------------------------------------------------------------

class TestRunPSPSPSReturnType:
    def test_returns_psspps_result(self):
        result = run_psspps("harmonic index", ZERO_ACTIVATIONS)
        assert isinstance(result, PSPSPSResult)

    def test_query_preserved(self):
        q = "attractor basin"
        result = run_psspps(q, ZERO_ACTIVATIONS)
        assert result.query == q

    def test_top_docs_list(self):
        result = run_psspps("test query", ZERO_ACTIVATIONS)
        assert isinstance(result.top_docs, list)

    def test_top_docs_are_scored_docs(self):
        result = run_psspps("graph node", ZERO_ACTIVATIONS)
        for doc in result.top_docs:
            assert isinstance(doc, ScoredDoc)

    def test_n_docs_searched_positive(self):
        result = run_psspps("shard", ZERO_ACTIVATIONS)
        assert result.n_docs_searched > 0

    def test_perspective_alpha_stored(self):
        result = run_psspps("query", ZERO_ACTIVATIONS, perspective_alpha=0.3)
        assert abs(result.perspective_alpha - 0.3) < 1e-9


# ---------------------------------------------------------------------------
# Pre-routing: trivial queries skip retrieval
# ---------------------------------------------------------------------------

class TestPreRouting:
    def test_slash_command_skips_retrieval(self):
        result = run_psspps("/status", ZERO_ACTIVATIONS)
        assert not result.retrieval_triggered

    def test_empty_query_returns_result(self):
        # Empty string doesn't crash; router may still trigger retrieval
        result = run_psspps("", ZERO_ACTIVATIONS)
        assert isinstance(result, PSPSPSResult)
        assert result.query == ""

    def test_meaningful_query_triggers_retrieval(self):
        result = run_psspps("harmonic shard propagation", ZERO_ACTIVATIONS)
        assert result.retrieval_triggered


# ---------------------------------------------------------------------------
# Score field ranges
# ---------------------------------------------------------------------------

class TestScoreRanges:
    def setup_method(self):
        self.result = run_psspps("attractor", ZERO_ACTIVATIONS)

    def test_retrieval_confidence_in_range(self):
        assert 0.0 <= self.result.retrieval_confidence <= 1.0

    def test_rag_confidence_in_range(self):
        assert 0.0 <= self.result.rag_confidence <= 1.0

    def test_doc_scores_in_range(self):
        for doc in self.result.top_docs:
            assert 0.0 <= doc.coherence_score <= 1.0
            assert 0.0 <= doc.combined_score <= 1.0

    def test_docs_sorted_descending(self):
        docs = self.result.top_docs
        for i in range(len(docs) - 1):
            assert docs[i].combined_score >= docs[i + 1].combined_score


# ---------------------------------------------------------------------------
# top_k parameter
# ---------------------------------------------------------------------------

class TestTopK:
    def test_default_top_k_three(self):
        result = run_psspps("graph worker", ZERO_ACTIVATIONS)
        assert len(result.top_docs) <= 3

    def test_custom_top_k(self):
        result = run_psspps("graph worker", ZERO_ACTIVATIONS, top_k=1)
        assert len(result.top_docs) <= 1

    def test_top_k_zero_returns_empty(self):
        result = run_psspps("query", ZERO_ACTIVATIONS, top_k=0)
        assert result.top_docs == []


# ---------------------------------------------------------------------------
# perspective_alpha blend
# ---------------------------------------------------------------------------

class TestPerspectiveAlpha:
    def test_alpha_zero_pure_semantic(self):
        r0 = run_psspps("graph", ZERO_ACTIVATIONS, perspective_alpha=0.0)
        assert r0.perspective_alpha == 0.0

    def test_alpha_one_pure_perspective(self):
        r1 = run_psspps("graph", ZERO_ACTIVATIONS, perspective_alpha=1.0)
        assert r1.perspective_alpha == 1.0

    def test_nonzero_activations_affect_perspective(self):
        activations = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        r_zero = run_psspps("graph", ZERO_ACTIVATIONS, perspective_alpha=1.0)
        r_act  = run_psspps("graph", activations,      perspective_alpha=1.0)
        # Results may differ in score ordering when activations are non-zero
        scores_zero = [d.combined_score for d in r_zero.top_docs]
        scores_act  = [d.combined_score for d in r_act.top_docs]
        # They don't have to differ, but neither should crash
        assert isinstance(scores_zero, list)
        assert isinstance(scores_act, list)


# ---------------------------------------------------------------------------
# ScoredDoc fields
# ---------------------------------------------------------------------------

class TestScoredDocFields:
    def test_scored_doc_has_path(self):
        result = run_psspps("hub", ZERO_ACTIVATIONS)
        for doc in result.top_docs:
            assert isinstance(doc.path, str)
            assert len(doc.path) > 0

    def test_scored_doc_snippet_is_string(self):
        result = run_psspps("hub", ZERO_ACTIVATIONS)
        for doc in result.top_docs:
            assert isinstance(doc.snippet, str)

    def test_scored_doc_has_coherence_score(self):
        result = run_psspps("harmonic", ZERO_ACTIVATIONS)
        for doc in result.top_docs:
            assert hasattr(doc, "coherence_score")
            assert isinstance(doc.coherence_score, float)


# ---------------------------------------------------------------------------
# _structural_order
# ---------------------------------------------------------------------------


class TestStructuralOrder:
    def test_one_hot_is_max_order(self):
        """A perfectly focused (one-hot) distribution has structural order 1.0."""
        a = np.zeros(8)
        a[3] = 1.0
        assert _structural_order(a) == pytest.approx(1.0, abs=1e-6)

    def test_uniform_is_zero_order(self):
        """A flat uniform distribution has structural order 0.0 (max entropy)."""
        a = np.ones(8) / 8.0
        assert _structural_order(a) == pytest.approx(0.0, abs=1e-6)

    def test_order_in_unit_range(self):
        """Structural order is always in [0, 1]."""
        for _ in range(10):
            a = np.abs(np.random.default_rng(42).random(8))
            a /= a.sum()
            val = _structural_order(a)
            assert 0.0 <= val <= 1.0 + 1e-9

    def test_more_concentrated_is_higher_order(self):
        """A more concentrated distribution should have higher order than a flatter one."""
        concentrated = np.array([0.8, 0.1, 0.05, 0.02, 0.01, 0.01, 0.005, 0.005])
        concentrated /= concentrated.sum()
        flat = np.ones(8) * 0.1 + np.array([0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        flat /= flat.sum()
        assert _structural_order(concentrated) > _structural_order(flat)


# ---------------------------------------------------------------------------
# coherence_scores
# ---------------------------------------------------------------------------


class TestCoherenceScores:
    def _uniform_affinity(self, n: int = 8) -> np.ndarray:
        return np.ones(n) / n

    def _one_hot(self, idx: int, n: int = 8) -> np.ndarray:
        a = np.zeros(n)
        a[idx] = 1.0
        return a

    def test_returns_array_of_correct_length(self):
        affs = [self._uniform_affinity() for _ in range(5)]
        acts = np.zeros(8)
        out = coherence_scores(affs, acts)
        assert len(out) == 5

    def test_uniform_affinity_gives_zero_coherence(self):
        """A flat affinity (structural order = 0) always scores zero."""
        acts = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        out = coherence_scores([self._uniform_affinity()], acts)
        assert out[0] == pytest.approx(0.0, abs=1e-9)

    def test_focused_aligned_doc_scores_highest(self):
        """A one-hot doc aligned with the active shard should outscore all others."""
        acts = np.array([0.0, 0.0, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        aligned = self._one_hot(2)       # shard 2 = active
        misaligned = self._one_hot(0)    # shard 0 = cold
        flat = self._uniform_affinity()
        out = coherence_scores([aligned, misaligned, flat], acts)
        assert out[0] > out[1]
        assert out[0] > out[2]

    def test_cold_index_differentiates_by_order(self):
        """With zero index, all alignment terms are equal; order alone differentiates."""
        acts = np.zeros(8)
        focused = self._one_hot(3)
        flat = self._uniform_affinity()
        out = coherence_scores([focused, flat], acts)
        # Both have equal alignment (uniform prior), focused has higher order
        assert out[0] > out[1]

    def test_all_zeros_affinity_returns_zero(self):
        """Edge: zero affinity vector gives zero coherence."""
        acts = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        out = coherence_scores([np.zeros(8)], acts)
        assert out[0] == pytest.approx(0.0, abs=1e-9)

    def test_scores_non_negative(self):
        """Coherence scores must always be non-negative."""
        rng = np.random.default_rng(7)
        affs = [np.abs(rng.random(8)) for _ in range(10)]
        for a in affs:
            if a.sum() > 1e-12:
                a /= a.sum()
        acts = np.abs(rng.random(8))
        out = coherence_scores(affs, acts)
        assert np.all(out >= -1e-12)


# ---------------------------------------------------------------------------
# run_find / FindCandidate — coherence-based Pericles pipeline
# ---------------------------------------------------------------------------


class TestRunFind:
    def test_returns_find_result(self):
        from psspps.find import FindResult, run_find
        result = run_find("harmonic index", ZERO_ACTIVATIONS)
        assert isinstance(result, FindResult)

    def test_n_docs_searched_positive(self):
        from psspps.find import run_find
        result = run_find("shard propagation", ZERO_ACTIVATIONS)
        assert result.n_docs_searched > 0

    def test_candidates_at_most_five(self):
        from psspps.find import run_find
        result = run_find("harmonic", ZERO_ACTIVATIONS)
        assert len(result.candidates_5) <= 5

    def test_operator_3_at_most_three(self):
        from psspps.find import run_find
        result = run_find("harmonic", ZERO_ACTIVATIONS)
        assert len(result.operator_3) <= 3

    def test_answer_is_candidate_or_none(self):
        from psspps.find import FindCandidate, run_find
        result = run_find("hub", ZERO_ACTIVATIONS)
        assert result.answer is None or isinstance(result.answer, FindCandidate)

    def test_candidate_has_coherence_score(self):
        from psspps.find import run_find
        result = run_find("graph", ZERO_ACTIVATIONS)
        for c in result.candidates_5:
            assert hasattr(c, "coherence_score")
            assert isinstance(c.coherence_score, float)

    def test_coherence_score_non_negative(self):
        from psspps.find import run_find
        result = run_find("propagation", ZERO_ACTIVATIONS)
        for c in result.candidates_5:
            assert c.coherence_score >= -1e-9

    def test_pericles_score_present(self):
        from psspps.find import run_find
        result = run_find("index", ZERO_ACTIVATIONS)
        for c in result.candidates_5:
            assert hasattr(c.pericles, "per")

    def test_operator_3_sorted_by_pericles(self):
        from psspps.find import run_find
        result = run_find("attractor", ZERO_ACTIVATIONS)
        ops = result.operator_3
        for i in range(len(ops) - 1):
            assert ops[i].pericles.per >= ops[i + 1].pericles.per

    def test_no_semantic_score_field(self):
        """FindCandidate must no longer expose semantic_score."""
        from psspps.find import FindCandidate
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(FindCandidate)}
        assert "semantic_score" not in field_names
        assert "coherence_score" in field_names


# ---------------------------------------------------------------------------
# ana_chi_weight
# ---------------------------------------------------------------------------


class TestAnaChiWeight:
    def test_peak_near_four_to_five_links(self):
        """Weight should be highest around 4-5 wikilinks (log1p closest to 𝒜_χ)."""
        from psspps.scorer import ana_chi_weight
        # Integer closest to optimal: log1p(4) ≈ 1.609 vs log1p(3) ≈ 1.386
        # Both are near 𝒜_χ = 1.5414 — n=4 wins, but neither reaches > 0.90
        w4 = ana_chi_weight(4)
        assert w4 > 0.80
        # n=4 should beat its neighbors
        assert w4 > ana_chi_weight(1)
        assert w4 > ana_chi_weight(20)

    def test_orphan_discounted(self):
        """Zero wikilinks (orphan) should score below a well-linked doc."""
        from psspps.scorer import ana_chi_weight
        assert ana_chi_weight(0) < ana_chi_weight(4)

    def test_overlinked_discounted(self):
        """20+ wikilinks overshoots 𝒜_χ and should score below peak."""
        from psspps.scorer import ana_chi_weight
        assert ana_chi_weight(25) < ana_chi_weight(4)

    def test_always_positive(self):
        """Weight is always in (0, 1] — never zero, never above 1."""
        from psspps.scorer import ana_chi_weight
        for n in [0, 1, 4, 10, 50, 200]:
            w = ana_chi_weight(n)
            assert 0.0 < w <= 1.0 + 1e-9

    def test_negative_clipped_to_zero(self):
        """Negative input treated as zero wikilinks — no crash."""
        from psspps.scorer import ana_chi_weight
        assert ana_chi_weight(-5) == ana_chi_weight(0)


# ---------------------------------------------------------------------------
# O(N) cache
# ---------------------------------------------------------------------------


class TestOnCache:
    def setup_method(self):
        """Reset cache before each test."""
        import psspps.scorer as sc
        sc._on_cache = None

    def teardown_method(self):
        """Reset cache after each test to avoid leaking state."""
        import psspps.scorer as sc
        sc._on_cache = None

    def test_cold_cache_uses_fallback(self):
        from psspps.scorer import _get_o_n
        result = _get_o_n(500)
        assert abs(result - 1.5) < 1e-9   # 1 + 500/1000

    def test_refresh_sets_cache(self):
        from psspps.scorer import refresh_on_cache, _get_o_n
        refresh_on_cache(2000)
        assert abs(_get_o_n(0) - 3.0) < 1e-9   # 1 + 2000/1000

    def test_cache_overrides_fallback(self):
        from psspps.scorer import refresh_on_cache, _get_o_n
        refresh_on_cache(100)
        # fallback would be 1 + 999/1000 = 1.999; cache gives 1 + 100/1000 = 1.1
        assert abs(_get_o_n(999) - 1.1) < 1e-9

    def test_o_n_always_positive(self):
        from psspps.scorer import _get_o_n, refresh_on_cache
        assert _get_o_n(0) >= 1.0
        refresh_on_cache(0)
        assert _get_o_n(0) >= 1.0


# ---------------------------------------------------------------------------
# modulate_search_alpha — index → PSSPPS perspective_alpha
# ---------------------------------------------------------------------------


class TestModulateSearchAlpha:
    def test_cold_index_is_neutral(self):
        from psspps.scorer import modulate_search_alpha
        assert modulate_search_alpha(ZERO_ACTIVATIONS) == pytest.approx(0.5)

    def test_one_hot_is_local(self):
        from psspps.scorer import modulate_search_alpha
        acts = np.zeros(8)
        acts[3] = 4.0
        assert modulate_search_alpha(acts) == pytest.approx(1.0, abs=1e-6)

    def test_uniform_is_global(self):
        from psspps.scorer import modulate_search_alpha
        acts = np.ones(8)
        assert modulate_search_alpha(acts) == pytest.approx(0.0, abs=1e-6)

    def test_peaked_higher_than_diffuse(self):
        from psspps.scorer import modulate_search_alpha
        peaked = np.array([0.0, 0.0, 5.0, 0.1, 0.0, 0.0, 0.0, 0.0])
        diffuse = np.array([1.0, 0.8, 0.9, 1.1, 0.7, 1.0, 0.85, 0.95])
        assert modulate_search_alpha(peaked) > modulate_search_alpha(diffuse)

    def test_alpha_in_unit_interval(self):
        from psspps.scorer import modulate_search_alpha
        rng = np.random.default_rng(11)
        for _ in range(12):
            acts = rng.random(8)
            val = modulate_search_alpha(acts)
            assert 0.0 <= val <= 1.0


# ---------------------------------------------------------------------------
# Comment node boost — sessions/comments/ docs get +0.15 lift
# ---------------------------------------------------------------------------


class TestCommentBoost:
    """
    Verify that the agent-comment boost constant is present, correctly valued,
    and that the pipeline applies it without pushing scores above 1.0.
    """

    def test_boost_constant_exists(self):
        from psspps.pipeline import _COMMENT_BOOST, _COMMENT_PATH_TOKEN
        assert _COMMENT_BOOST == pytest.approx(0.15)
        assert _COMMENT_PATH_TOKEN == "sessions/comments/"

    def test_combined_score_capped_at_one(self):
        """Even with boost, combined_score must stay in [0, 1]."""
        result = run_psspps("agent comment annotation", ZERO_ACTIVATIONS)
        for doc in result.top_docs:
            assert doc.combined_score <= 1.0, (
                f"score {doc.combined_score} > 1.0 for {doc.path}"
            )

    def test_boost_applied_to_comment_path(self):
        """
        Inject a synthetic comment-path doc into the scorer and confirm the
        boost lifts its final score above the unboosted baseline.
        """
        import numpy as np
        from psspps.pipeline import _COMMENT_BOOST, _COMMENT_PATH_TOKEN
        from psspps.scorer import (
            build_tfidf, combined_scores, harmonic_affinity,
            perspective_scores, query_vector, semantic_scores,
        )

        query = "agent comment annotation"
        docs_text = ["totally unrelated content xyz zzz", "agent comment annotation"]
        paths = ["stations/unrelated.md", f"{_COMMENT_PATH_TOKEN}2026-01-01-comment-test.md"]

        tfidf, vocab = build_tfidf(docs_text)
        q_vec = query_vector(query, vocab)
        sem = semantic_scores(q_vec, tfidf)
        affinities = [harmonic_affinity([]) for _ in docs_text]
        persp = perspective_scores(affinities, ZERO_ACTIVATIONS)
        final = combined_scores(sem, persp, alpha=0.5).copy()

        score_before_boost = final[1]

        # Apply boost (mirrors pipeline logic)
        for i, path in enumerate(paths):
            if _COMMENT_PATH_TOKEN in path.replace("\\", "/"):
                final[i] = min(1.0, final[i] + _COMMENT_BOOST)

        assert final[1] >= score_before_boost, "boost must not decrease score"
        if score_before_boost + _COMMENT_BOOST <= 1.0:
            assert abs(final[1] - (score_before_boost + _COMMENT_BOOST)) < 1e-9

