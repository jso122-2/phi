"""
Tests for psspps.traverser (minecart graph traversal).

All tests are fastembed-free: they supply pre-built numpy arrays
and synthetic VaultDoc dicts, so they run offline with zero model
weights required.
"""
from __future__ import annotations

import numpy as np
import pytest

from psspps.traverser import TraversalResult, find_doc_by_title, traverse

# ---------------------------------------------------------------------------
# Fixtures — synthetic vault
# ---------------------------------------------------------------------------

_N = 6  # number of synthetic docs
_DIM = 8  # small embedding dimension for speed


def _make_docs(n: int = _N) -> list[dict]:
    titles = [f"doc_{i}" for i in range(n)]
    texts = [f"This is document {i} about topic {i}." for i in range(n)]
    return [
        {
            "title": t,
            "path": f"{t}.md",
            "text": tx,
            "clean_text": tx,
            "headings": [],
            "wikilinks": [],
            "numbers": [],
        }
        for t, tx in zip(titles, texts)
    ]


def _unit(v: np.ndarray) -> np.ndarray:
    return v / (np.linalg.norm(v) + 1e-12)


def _orthonormal(n: int, d: int, seed: int = 0) -> np.ndarray:
    """Create n orthonormal-ish vectors in R^d for controlled similarity."""
    rng = np.random.default_rng(seed)
    raw = rng.standard_normal((n, d)).astype(np.float32)
    for i in range(n):
        raw[i] = _unit(raw[i])
    return raw


def _stub_embed(texts: list[str], d: int = _DIM, seed: int = 42) -> np.ndarray:
    """Deterministic stub embedder — no fastembed, no model weights."""
    rng = np.random.default_rng(seed + len(texts))
    vecs = rng.standard_normal((len(texts), d)).astype(np.float32)
    for i in range(len(texts)):
        vecs[i] = _unit(vecs[i])
    return vecs


def _make_embed_fn(d: int = _DIM):
    return lambda texts: _stub_embed(texts, d=d)


# ---------------------------------------------------------------------------
# find_doc_by_title
# ---------------------------------------------------------------------------


class TestFindDocByTitle:
    def test_exact_match(self):
        docs = _make_docs()
        assert find_doc_by_title(docs, "doc_2") == 2

    def test_case_insensitive(self):
        docs = _make_docs()
        assert find_doc_by_title(docs, "DOC_3") == 3

    def test_missing(self):
        docs = _make_docs()
        assert find_doc_by_title(docs, "nonexistent") == -1


# ---------------------------------------------------------------------------
# TraversalResult.to_dict
# ---------------------------------------------------------------------------


class TestTraversalResultToDict:
    def test_empty_result(self):
        r = TraversalResult(seed="test")
        d = r.to_dict()
        assert d["seed"] == "test"
        assert d["path"] == []
        assert d["n_hops"] == 0
        assert d["hops"] == []
        assert d["total_chars"] == 0

    def test_hop_fields(self):
        from psspps.traverser import Hop

        r = TraversalResult(seed="x")
        r.hops.append(Hop(index=0, title="a", similarity=0.9, chars_added=10, budget_remaining=90))
        r.path.append("a")
        d = r.to_dict()
        hop = d["hops"][0]
        assert hop["title"] == "a"
        assert hop["similarity"] == pytest.approx(0.9)
        assert hop["chars_added"] == 10


# ---------------------------------------------------------------------------
# traverse — core minecart logic
# ---------------------------------------------------------------------------


class TestTraverse:
    def test_returns_traversal_result(self):
        docs = _make_docs()
        embs = _orthonormal(_N, _DIM)
        seed = "query about topic 0"
        result = traverse(seed, docs, embs, max_hops=3, context_budget=200, embed_fn=_make_embed_fn())
        assert isinstance(result, TraversalResult)

    def test_visits_at_most_max_hops(self):
        docs = _make_docs()
        embs = _orthonormal(_N, _DIM)
        result = traverse("query", docs, embs, max_hops=2, context_budget=10_000, embed_fn=_make_embed_fn())
        assert len(result.hops) <= 2

    def test_seed_title_boards_first(self):
        docs = _make_docs()
        embs = _orthonormal(_N, _DIM)
        result = traverse("doc_1", docs, embs, max_hops=4, context_budget=10_000, embed_fn=_make_embed_fn())
        assert result.path[0] == "doc_1"

    def test_no_revisit(self):
        docs = _make_docs()
        embs = _orthonormal(_N, _DIM)
        result = traverse("query", docs, embs, max_hops=_N, context_budget=10_000, embed_fn=_make_embed_fn())
        assert len(result.path) == len(set(result.path))

    def test_budget_limits_traversal(self):
        docs = _make_docs()
        embs = _orthonormal(_N, _DIM)
        result = traverse("query", docs, embs, max_hops=8, context_budget=1, embed_fn=_make_embed_fn())
        assert result.total_chars <= 1 or "budget" in result.stopped_reason

    def test_stopped_reason_set(self):
        docs = _make_docs()
        embs = _orthonormal(_N, _DIM)
        result = traverse("query", docs, embs, max_hops=2, context_budget=10_000, embed_fn=_make_embed_fn())
        assert result.stopped_reason != ""

    def test_path_matches_hops(self):
        docs = _make_docs()
        embs = _orthonormal(_N, _DIM)
        result = traverse("query", docs, embs, max_hops=4, context_budget=10_000, embed_fn=_make_embed_fn())
        assert len(result.path) == len(result.hops)

    def test_similarity_in_range(self):
        docs = _make_docs()
        embs = _orthonormal(_N, _DIM)
        result = traverse("query", docs, embs, max_hops=4, context_budget=10_000, embed_fn=_make_embed_fn())
        for hop in result.hops:
            assert -1.0 <= hop.similarity <= 1.0 + 1e-6

    def test_sim_floor_respected(self):
        """With sim_floor=1.0 only perfect matches pass — cart stops immediately."""
        docs = _make_docs()
        embs = _orthonormal(_N, _DIM)
        result = traverse("query", docs, embs, max_hops=4, context_budget=10_000, sim_floor=1.0, embed_fn=_make_embed_fn())
        for hop in result.hops[1:]:
            assert hop.similarity >= 1.0

    def test_empty_docs_handled(self):
        result = traverse("seed", [], np.zeros((0, _DIM), dtype=np.float32), max_hops=4, embed_fn=_make_embed_fn())
        assert result.path == []
        assert result.hops == []
