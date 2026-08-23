"""
Tests for the Stage II QueryRouter — phi/models/query_router.py.

Synthetic corpus only; no real library or disk I/O.
"""
from __future__ import annotations

import pytest

from phi.models.query_router import QueryRouter, RouteAction, RouteDecision


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SMALL_CORPUS = [
    "jazz piano soul music blue note",
    "electronic techno synth beats",
    "ambient drone atmospheric texture",
    "rock guitar heavy distortion",
    "classical violin orchestra symphony",
    "hip hop rap beats sampling",
    "reggae dub bass rhythm",
    "funk groove bass disco dance",
]

LARGE_CORPUS = SMALL_CORPUS * 4  # 32 docs


def fitted_router(corpus: list[str] | None = None, **kwargs) -> QueryRouter:
    r = QueryRouter(**kwargs)
    r.fit(corpus if corpus is not None else SMALL_CORPUS)
    return r


# ---------------------------------------------------------------------------
# is_fitted
# ---------------------------------------------------------------------------


class TestIsFitted:
    def test_false_before_fit(self):
        r = QueryRouter()
        assert r.is_fitted is False

    def test_true_after_fit(self):
        r = QueryRouter()
        r.fit(SMALL_CORPUS)
        assert r.is_fitted is True

    def test_true_after_fit_empty_corpus(self):
        r = QueryRouter()
        r.fit([])
        assert r.is_fitted is True


# ---------------------------------------------------------------------------
# route() before fit() raises
# ---------------------------------------------------------------------------


class TestRouteBeforeFit:
    def test_raises_runtime_error(self):
        r = QueryRouter()
        with pytest.raises(RuntimeError, match="fit"):
            r.route("jazz music")


# ---------------------------------------------------------------------------
# PASSTHROUGH cases
# ---------------------------------------------------------------------------


class TestPassthrough:
    def test_empty_query(self):
        r = fitted_router()
        decision = r.route("")
        assert decision.action == RouteAction.PASSTHROUGH
        assert decision.cluster_id == -1
        assert decision.confidence == 0.0

    def test_single_token_query(self):
        r = fitted_router(min_tokens=2)
        decision = r.route("jazz")
        assert decision.action == RouteAction.PASSTHROUGH
        assert decision.cluster_id == -1

    def test_low_score_query_passthrough(self):
        # A query with zero overlap with the corpus vocab should produce near-zero
        # cosine similarity against every centroid → PASSTHROUGH.
        r = fitted_router(min_score=0.05)
        # Use gibberish tokens that cannot appear in SMALL_CORPUS
        decision = r.route("zzxyz qqqwww pppnnn mmmlll")
        assert decision.action == RouteAction.PASSTHROUGH
        assert decision.cluster_id == -1

    def test_passthrough_tokens_still_populated(self):
        # Even a single-token PASSTHROUGH should expose query_tokens
        r = fitted_router(min_tokens=2)
        decision = r.route("jazz")
        # tokenize("jazz") = ["jazz"]
        assert isinstance(decision.query_tokens, list)

    def test_passthrough_confidence_zero_empty(self):
        r = fitted_router()
        decision = r.route("")
        assert decision.confidence == 0.0


# ---------------------------------------------------------------------------
# SEARCH cases
# ---------------------------------------------------------------------------


class TestSearch:
    def test_search_action(self):
        r = fitted_router()
        decision = r.route("jazz piano soul")
        assert decision.action == RouteAction.SEARCH

    def test_cluster_id_in_range(self):
        r = fitted_router(n_clusters=8)
        decision = r.route("jazz piano soul")
        assert 0 <= decision.cluster_id < 8

    def test_confidence_in_unit_range(self):
        r = fitted_router()
        decision = r.route("jazz piano soul")
        assert 0.0 < decision.confidence <= 1.0

    def test_query_tokens_populated(self):
        r = fitted_router()
        decision = r.route("jazz piano soul")
        assert isinstance(decision.query_tokens, list)
        assert len(decision.query_tokens) > 0
        assert "jazz" in decision.query_tokens

    def test_returns_route_decision(self):
        r = fitted_router()
        decision = r.route("electronic techno beats")
        assert isinstance(decision, RouteDecision)

    def test_search_on_large_corpus(self):
        r = fitted_router(corpus=LARGE_CORPUS, n_clusters=8)
        decision = r.route("hip hop rap beats")
        assert decision.action == RouteAction.SEARCH
        assert 0 <= decision.cluster_id < 8
        assert decision.confidence > 0.0

    def test_min_score_zero_forces_search_if_any_overlap(self):
        # With min_score=0.0, any non-empty query with corpus overlap → SEARCH
        r = fitted_router(min_score=0.0)
        decision = r.route("jazz piano")
        assert decision.action == RouteAction.SEARCH


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_fewer_docs_than_clusters_no_crash(self):
        # 3 docs, 8 clusters → some centroids are all-zero vectors
        sparse_corpus = [
            "jazz piano soul",
            "electronic techno",
            "rock guitar",
        ]
        r = QueryRouter(n_clusters=8)
        r.fit(sparse_corpus)
        assert r.is_fitted
        # Routing should not crash
        decision = r.route("jazz piano")
        assert decision.action in {RouteAction.SEARCH, RouteAction.PASSTHROUGH}

    def test_single_doc_corpus(self):
        r = QueryRouter(n_clusters=8)
        r.fit(["jazz piano soul"])
        assert r.is_fitted
        decision = r.route("jazz piano")
        assert isinstance(decision, RouteDecision)

    def test_empty_corpus_passthrough(self):
        r = QueryRouter()
        r.fit([])
        # After fitting on empty corpus, any query should come back PASSTHROUGH
        # because cosine sims will all be 0 → below min_score
        decision = r.route("jazz piano soul bass")
        assert decision.action == RouteAction.PASSTHROUGH

    def test_repr_unfitted(self):
        r = QueryRouter()
        assert "unfitted" in repr(r)

    def test_repr_fitted(self):
        r = fitted_router()
        assert "fitted" in repr(r)

    def test_n_clusters_param(self):
        r = fitted_router(n_clusters=4, corpus=LARGE_CORPUS)
        decision = r.route("jazz piano soul")
        if decision.action == RouteAction.SEARCH:
            assert 0 <= decision.cluster_id < 4

    def test_route_decision_dataclass_fields(self):
        r = fitted_router()
        d = r.route("jazz piano soul")
        assert hasattr(d, "action")
        assert hasattr(d, "cluster_id")
        assert hasattr(d, "confidence")
        assert hasattr(d, "query_tokens")
