"""
Tests for engine/vault_garden.py

Covers:
  - build_adjacency: wikilinks produce correct symmetric matrix
  - build_adjacency: path-prefixed links are resolved
  - build_adjacency: self-loops are absent
  - project_embeddings: output shape and no-op when d_in == d_out
  - _node_text: title + truncated body
  - VaultGarden.run_cycle: runs end-to-end with stub vault (no fastembed)
  - VaultGarden.run_cycle: returns zero summary on empty vault
  - VaultGarden: tick advances after each cycle
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from engine.vault_garden import (
    build_adjacency,
    project_embeddings,
    _node_text,
    VaultGarden,
)


# ---------------------------------------------------------------------------
# Minimal VaultNode stub — avoids disk I/O
# ---------------------------------------------------------------------------

@dataclass
class _Node:
    path: Path = Path("stub.md")
    title: str = "stub"
    tags: list = field(default_factory=list)
    wikilinks: list = field(default_factory=list)
    text: str = ""

    @property
    def stem(self) -> str:
        return self.path.stem


# ---------------------------------------------------------------------------
# build_adjacency
# ---------------------------------------------------------------------------

class TestBuildAdjacency:
    def test_bare_link_produces_edge(self):
        a = _Node(Path("alpha.md"), title="alpha", wikilinks=["beta"])
        b = _Node(Path("beta.md"),  title="beta")
        A = build_adjacency([a, b])
        assert A[0, 1] == 1.0
        assert A[1, 0] == 1.0   # symmetric

    def test_path_prefixed_link_resolved(self):
        a = _Node(Path("alpha.md"), title="alpha", wikilinks=["keep/beta"])
        b = _Node(Path("beta.md"),  title="beta")
        A = build_adjacency([a, b])
        assert A[0, 1] == 1.0

    def test_no_self_loop(self):
        a = _Node(Path("alpha.md"), title="alpha", wikilinks=["alpha"])
        A = build_adjacency([a])
        assert A[0, 0] == 0.0

    def test_missing_target_no_edge(self):
        a = _Node(Path("alpha.md"), title="alpha", wikilinks=["ghost"])
        A = build_adjacency([a])
        assert A.sum() == 0.0

    def test_shape(self):
        nodes = [_Node(Path(f"n{i}.md"), title=f"n{i}") for i in range(5)]
        A = build_adjacency(nodes)
        assert A.shape == (5, 5)

    def test_symmetric(self):
        a = _Node(Path("a.md"), title="a", wikilinks=["b"])
        b = _Node(Path("b.md"), title="b")
        A = build_adjacency([a, b])
        np.testing.assert_array_equal(A, A.T)


# ---------------------------------------------------------------------------
# project_embeddings
# ---------------------------------------------------------------------------

class TestProjectEmbeddings:
    def test_output_shape(self):
        X = np.random.randn(10, 384).astype(np.float32)
        out = project_embeddings(X, d_out=256)
        assert out.shape == (10, 256)

    def test_noop_when_same_dim(self):
        X = np.eye(8, dtype=np.float32)
        out = project_embeddings(X, d_out=8)
        np.testing.assert_allclose(out, X.astype(np.float64))

    def test_deterministic(self):
        X = np.random.randn(5, 100).astype(np.float32)
        a = project_embeddings(X, d_out=32, seed=1)
        b = project_embeddings(X, d_out=32, seed=1)
        np.testing.assert_array_equal(a, b)

    def test_different_seeds_differ(self):
        X = np.random.randn(5, 100).astype(np.float32)
        a = project_embeddings(X, d_out=32, seed=1)
        b = project_embeddings(X, d_out=32, seed=2)
        assert not np.allclose(a, b)


# ---------------------------------------------------------------------------
# _node_text
# ---------------------------------------------------------------------------

class TestNodeText:
    def test_combines_title_and_body(self):
        n = _Node(title="My Node", text="Some content here.")
        t = _node_text(n)
        assert t.startswith("My Node")
        assert "Some content" in t

    def test_truncates_long_text(self):
        n = _Node(title="T", text="x" * 1000)
        t = _node_text(n)
        # Body portion should be ≤ 512 chars; total should be short
        assert len(t) < 600


# ---------------------------------------------------------------------------
# VaultGarden.run_cycle
# ---------------------------------------------------------------------------

class TestVaultGardenRunCycle:
    def _make_nodes(self, n: int = 5):
        nodes = []
        for i in range(n):
            wikilinks = [f"n{(i+1) % n}"]   # ring graph
            nodes.append(_Node(
                path=Path(f"n{i}.md"), title=f"n{i}",
                wikilinks=wikilinks, text=f"content of node {i}",
            ))
        return nodes

    def _fake_embed(self, nodes, batch_size=64):
        """Stub: returns fixed 384-d embeddings without fastembed."""
        rng = np.random.default_rng(0)
        return rng.standard_normal((len(nodes), 384)).astype(np.float32)

    def test_returns_tracer_summary(self, tmp_path):
        nodes = self._make_nodes(6)
        with patch("engine.vault_garden.embed_nodes", side_effect=self._fake_embed):
            garden = VaultGarden(vault_root=tmp_path, d_model=64, max_tracers=2)
            summary = garden.run_cycle(vault=nodes)
        assert summary.n_tracers >= 1
        assert 0.0 <= summary.mean_coherence <= 1.0

    def test_tick_advances(self, tmp_path):
        nodes = self._make_nodes(4)
        with patch("engine.vault_garden.embed_nodes", side_effect=self._fake_embed):
            garden = VaultGarden(vault_root=tmp_path, d_model=64, max_tracers=2)
            garden.run_cycle(vault=nodes)
            assert garden.tick == 1
            garden.run_cycle(vault=nodes)
            assert garden.tick == 2

    def test_empty_vault_returns_zero_summary(self, tmp_path):
        garden = VaultGarden(vault_root=tmp_path, d_model=64)
        summary = garden.run_cycle(vault=[])
        assert summary.n_tracers == 0
        assert summary.arm_prune == 0.0

    def test_samba_dir_created(self, tmp_path):
        nodes = self._make_nodes(4)
        with patch("engine.vault_garden.embed_nodes", side_effect=self._fake_embed):
            garden = VaultGarden(vault_root=tmp_path, d_model=64, max_tracers=1)
            garden.run_cycle(vault=nodes)
        # SambaWriter creates the directory at construction time
        assert garden.samba_dir.exists()
