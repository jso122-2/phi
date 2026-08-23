"""
Tests for graph/worker.py

Covers:
  - _resolve_link strips path prefix (regression for dead-link false-positive bug)
  - run_clean: path-prefixed links count as live, not dead
  - run_clean: only truly absent stems are reported as dead links
  - run_clean: orphan detection uses resolved stems
  - run_status: zero dead links for path-prefixed vault
  - run_nest: structural hubs are excluded from suggestions
  - run_nest: at least one semantic hub suggested when shared links exist
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

import pytest

from graph.worker import _resolve_link, run_clean, run_nest, run_status


# ---------------------------------------------------------------------------
# Minimal VaultNode stub — avoids hitting disk
# ---------------------------------------------------------------------------

@dataclass
class _Node:
    stem: str
    rel_path: str = ""
    tags: list[str] = field(default_factory=list)
    wikilinks: list[str] = field(default_factory=list)
    text: str = ""


def _vault(*nodes: _Node):
    return list(nodes)


# ---------------------------------------------------------------------------
# _resolve_link
# ---------------------------------------------------------------------------

class TestResolveLink:
    def _idx(self, *stems: str) -> tuple[dict[str, str], set[str]]:
        """Build (path_index, stems) from bare stems."""
        st = set(stems)
        idx = {s: s for s in stems}
        return idx, st

    def test_bare_stem_unchanged(self):
        idx, st = self._idx("foo-bar")
        assert _resolve_link("foo-bar", idx, st) == "foo-bar"

    def test_single_prefix_stripped(self):
        idx, st = self._idx("foo-bar")
        assert _resolve_link("keep/foo-bar", idx, st) == "foo-bar"

    def test_deep_prefix_stripped(self):
        idx, st = self._idx("foo-bar")
        assert _resolve_link("sessions/ingest/foo-bar", idx, st) == "foo-bar"

    def test_empty_string(self):
        idx, st = self._idx()
        assert _resolve_link("", idx, st) is None

    def test_unknown_link_returns_none(self):
        idx, st = self._idx("alpha")
        assert _resolve_link("missing", idx, st) is None


# ---------------------------------------------------------------------------
# run_clean — dead link detection
# ---------------------------------------------------------------------------

class TestRunCleanDeadLinks:
    def test_bare_stem_link_is_live(self):
        a = _Node("alpha", wikilinks=["beta"])
        b = _Node("beta")
        report = run_clean(_vault(a, b))
        assert report.dead_links == []

    def test_path_prefixed_link_is_live(self):
        """keep/beta links to beta — should NOT be reported as dead (regression test)."""
        a = _Node("alpha", wikilinks=["keep/beta"])
        b = _Node("beta")
        report = run_clean(_vault(a, b))
        assert report.dead_links == []

    def test_absent_target_is_dead(self):
        a = _Node("alpha", wikilinks=["nonexistent"])
        report = run_clean(_vault(a))
        assert len(report.dead_links) == 1
        assert "nonexistent" in report.dead_links[0]

    def test_deep_path_prefix_is_live(self):
        a = _Node("alpha", wikilinks=["sessions/ingest/gamma"])
        b = _Node("gamma")
        report = run_clean(_vault(a, b))
        assert report.dead_links == []

    def test_mixed_live_and_dead(self):
        a = _Node("alpha", wikilinks=["keep/beta", "ghost"])
        b = _Node("beta")
        report = run_clean(_vault(a, b))
        assert len(report.dead_links) == 1
        assert "ghost" in report.dead_links[0]


# ---------------------------------------------------------------------------
# run_clean — orphan detection
# ---------------------------------------------------------------------------

class TestRunCleanOrphans:
    def test_linked_node_not_orphan(self):
        hub = _Node("HOME", tags=["hub"])
        a = _Node("alpha", wikilinks=["HOME"])
        b = _Node("beta", wikilinks=["alpha"])
        report = run_clean(_vault(hub, a, b))
        # alpha is linked by beta → not orphan; beta has no incoming → orphan
        assert "alpha" not in report.orphans
        assert "beta" in report.orphans

    def test_path_prefixed_link_counts_as_incoming(self):
        """beta links to keep/alpha — alpha should have 1 incoming, not be an orphan."""
        a = _Node("alpha")
        b = _Node("beta", wikilinks=["keep/alpha"])
        report = run_clean(_vault(a, b))
        assert "alpha" not in report.orphans

    def test_hub_never_orphan(self):
        hub = _Node("HOME", tags=["hub"])
        report = run_clean(_vault(hub))
        assert "HOME" not in report.orphans

    def test_session_never_orphan(self):
        s = _Node("2025-01-01-session", tags=["session"])
        report = run_clean(_vault(s))
        assert "2025-01-01-session" not in report.orphans


# ---------------------------------------------------------------------------
# run_status
# ---------------------------------------------------------------------------

class TestRunStatus:
    def test_zero_dead_links_for_path_prefixed_vault(self):
        a = _Node("alpha", wikilinks=["keep/beta", "keep/gamma"])
        b = _Node("beta")
        c = _Node("gamma")
        status = run_status(_vault(a, b, c))
        assert status.n_dead_links == 0

    def test_counts_nodes_correctly(self):
        nodes = [_Node(f"node-{i}") for i in range(10)]
        status = run_status(nodes)
        assert status.n_nodes == 10

    def test_hub_count(self):
        nodes = [_Node(f"h{i}", tags=["hub"]) for i in range(3)] + [_Node("leaf")]
        status = run_status(nodes)
        assert status.n_hubs == 3

    def test_session_count(self):
        nodes = [_Node(f"s{i}", tags=["session"]) for i in range(5)] + [_Node("leaf")]
        status = run_status(nodes)
        assert status.n_session_nodes == 5

    def test_most_linked_ordered(self):
        popular = _Node("popular")
        # Three nodes link to popular
        linkers = [_Node(f"l{i}", wikilinks=["popular"]) for i in range(3)]
        status = run_status([popular] + linkers)
        stems = [stem for stem, _ in status.most_linked]
        assert stems[0] == "popular"

    def test_orphan_count_with_path_prefix(self):
        """
        Path-prefixed links are resolved correctly so `leaf` is not an orphan.
        `linker` has no incoming links and IS a genuine orphan.
        """
        hub = _Node("HOME", tags=["hub"])
        leaf = _Node("leaf", wikilinks=["HOME"])
        linker = _Node("linker", wikilinks=["keep/leaf"])
        # Add a node that links to linker so linker is also reachable
        root = _Node("root", wikilinks=["linker"])
        status = run_status([hub, leaf, linker, root])
        # root has no incoming links → it is the only orphan
        assert status.n_orphans == 1
        assert status.n_dead_links == 0


# ---------------------------------------------------------------------------
# run_nest — structural hub exclusion
# ---------------------------------------------------------------------------

class TestRunNest:
    _STRUCTURAL = ["index", "sessions", "git-log", "live-state", "graph", "keep"]

    def test_structural_hubs_excluded_from_suggestions(self):
        structural = [_Node(s, tags=["hub"], wikilinks=["leaf"]) for s in self._STRUCTURAL]
        leaf = _Node("leaf", wikilinks=["index"])
        report = run_nest(structural + [leaf])
        suggested_hubs = {s["suggested_hub"] for s in report.suggestions}
        assert not suggested_hubs.intersection(self._STRUCTURAL)

    def test_semantic_hub_suggested_when_links_shared(self):
        home = _Node("HOME", tags=["hub"], wikilinks=["shared-note"])
        leaf = _Node("leaf", wikilinks=["shared-note"])
        report = run_nest([home, leaf])
        assert any(s["suggested_hub"] == "HOME" for s in report.suggestions)

    def test_no_suggestions_when_no_semantic_hubs(self):
        structural = [_Node(s, tags=["hub"]) for s in self._STRUCTURAL]
        leaf = _Node("leaf")
        report = run_nest(structural + [leaf])
        assert report.suggestions == [] or all(
            s["suggested_hub"] not in self._STRUCTURAL
            for s in report.suggestions
        )

    def test_hub_itself_not_in_suggestions(self):
        home = _Node("HOME", tags=["hub"])
        leaf = _Node("leaf")
        report = run_nest([home, leaf])
        suggested_nodes = {s["node"] for s in report.suggestions}
        assert "HOME" not in suggested_nodes
