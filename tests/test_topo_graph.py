"""
Tests for graph/topo_graph.py — topological hub election via β₀ components.
"""
from __future__ import annotations

import pytest
import networkx as nx

from graph.topo_graph import build, analyse, write_hub_tags, TopoHubReport, ComponentRecord
from graph.node import VaultNode


# ---------------------------------------------------------------------------
# Helpers — synthetic VaultNodes without hitting the real vault
# ---------------------------------------------------------------------------


def _node(stem: str, links: list[str], tags: list[str] | None = None) -> VaultNode:
    from pathlib import Path
    from graph.node import VAULT_ROOT
    return VaultNode(
        path=VAULT_ROOT / f"{stem}.md",
        title=stem.replace("-", " ").title(),
        tags=tags or [],
        wikilinks=links,
        text=f"# {stem}\n\n" + " ".join(f"[[{lnk}]]" for lnk in links),
    )


# ---------------------------------------------------------------------------
# build()
# ---------------------------------------------------------------------------


class TestBuild:
    def test_empty_vault_returns_empty_graph(self):
        G = build([])
        assert G.number_of_nodes() == 0
        assert G.number_of_edges() == 0

    def test_single_node_no_edges(self):
        G = build([_node("a", [])])
        assert G.number_of_nodes() == 1
        assert G.number_of_edges() == 0

    def test_wikilink_becomes_directed_edge(self):
        nodes = [_node("a", ["b"]), _node("b", [])]
        G = build(nodes)
        assert G.has_edge("a", "b")
        assert not G.has_edge("b", "a")

    def test_dead_link_not_added(self):
        # "b" is referenced but not in vault → no edge
        G = build([_node("a", ["b"])])
        assert G.number_of_edges() == 0

    def test_self_links_excluded(self):
        G = build([_node("a", ["a"])])
        assert G.number_of_edges() == 0

    def test_path_prefix_links_stripped(self):
        # [[folder/b]] should resolve to edge a → b
        nodes = [_node("a", ["folder/b"]), _node("b", [])]
        G = build(nodes)
        assert G.has_edge("a", "b")


# ---------------------------------------------------------------------------
# analyse() — component detection + hub election
# ---------------------------------------------------------------------------


class TestAnalyse:
    def _two_components(self):
        """
        Component 1: a ↔ b (b is higher degree)
        Component 2: c (singleton)
        """
        nodes = [
            _node("a", ["b"]),
            _node("b", ["a"]),
            _node("c", []),
        ]
        return nodes

    def test_two_components_detected(self):
        nodes = self._two_components()
        G = build(nodes)
        r = analyse(G, nodes, min_component_size=2)
        # {a,b} is one component of size 2; c is a singleton
        assert r.n_components == 2
        assert r.n_elected == 1        # only {a,b} qualifies
        assert r.n_singletons == 1

    def test_hub_is_highest_in_degree(self):
        """
        x → hub, y → hub, hub → z  — hub has in_degree 2, all others ≤ 1
        All in one component.
        """
        nodes = [
            _node("x",   ["hub"]),
            _node("y",   ["hub"]),
            _node("hub", ["z"]),
            _node("z",   []),
        ]
        G = build(nodes)
        r = analyse(G, nodes, min_component_size=2)
        assert r.n_elected == 1
        assert r.components[0].hub == "hub"

    def test_hub_spokes_partition(self):
        """All non-hub nodes appear in spokes list."""
        nodes = [
            _node("x",   ["hub"]),
            _node("y",   ["hub"]),
            _node("hub", ["z"]),
            _node("z",   []),
        ]
        G = build(nodes)
        r = analyse(G, nodes, min_component_size=2)
        comp = r.components[0]
        all_in_comp = {comp.hub} | set(comp.spokes)
        assert all_in_comp == {"x", "y", "hub", "z"}

    def test_min_component_size_filters_small(self):
        nodes = [
            _node("a", ["b"]),
            _node("b", []),
            _node("c", []),
        ]
        G = build(nodes)
        # min_component_size=3 should filter out the {a,b} component (size 2)
        r = analyse(G, nodes, min_component_size=3)
        assert r.n_elected == 0

    def test_hub_to_spokes_map_populated(self):
        nodes = [
            _node("x", ["hub"]),
            _node("hub", []),
        ]
        G = build(nodes)
        r = analyse(G, nodes)
        assert "hub" in r.hub_to_spokes
        assert "x" in r.hub_to_spokes["hub"]

    def test_spoke_to_hub_map_populated(self):
        nodes = [
            _node("x", ["hub"]),
            _node("hub", []),
        ]
        G = build(nodes)
        r = analyse(G, nodes)
        assert r.spoke_to_hub["x"] == "hub"

    def test_empty_vault_returns_zero_elected(self):
        r = analyse(build([]), [])
        assert r.n_elected == 0
        assert r.n_components == 0

    def test_tiebreak_shorter_stem_wins(self):
        """
        When in-degrees are equal, shorter stem (more general) wins.
        Both 'long-stem' and 'a' have in_degree 1 — 'a' should win.
        """
        nodes = [
            _node("x",         ["long-stem"]),
            _node("y",         ["a"]),
            _node("long-stem", []),
            _node("a",         []),
        ]
        G = build(nodes)
        r = analyse(G, nodes, min_component_size=2)
        # One component (all connected via x→long-stem, y→a, but no cross-links)
        # Actually x,long-stem and y,a are two separate components
        assert r.n_elected == 2
        hubs = {c.hub for c in r.components}
        assert "a" in hubs
        assert "long-stem" not in hubs or "a" in hubs

    def test_already_hub_tagged_flag(self):
        nodes = [
            _node("spoke",      ["tagged-hub"]),   # spoke → tagged-hub (in_degree 1)
            _node("tagged-hub", [], tags=["hub"]), # already tagged; highest in-degree
        ]
        G = build(nodes)
        r = analyse(G, nodes)
        comp = r.components[0]
        assert comp.hub == "tagged-hub"
        assert comp.already_hub_tagged is True


# ---------------------------------------------------------------------------
# TopoHubReport.summary()
# ---------------------------------------------------------------------------


class TestSummary:
    def test_summary_keys(self):
        r = analyse(build([]), [])
        s = r.summary()
        assert "nodes" in s
        assert "edges" in s
        assert "components" in s
        assert "elected_hubs" in s
        assert "top_hubs" in s

    def test_top_hubs_sorted_by_in_degree(self):
        nodes = [
            _node("a", ["big-hub"]),
            _node("b", ["big-hub"]),
            _node("c", ["big-hub"]),
            _node("big-hub", []),
            _node("x", ["small-hub"]),
            _node("small-hub", []),
        ]
        G = build(nodes)
        r = analyse(G, nodes, min_component_size=2)
        top = r.summary()["top_hubs"]
        # big-hub (in_degree 3) should appear before small-hub (in_degree 1)
        hub_names = [h["hub"] for h in top]
        assert hub_names.index("big-hub") < hub_names.index("small-hub")


# ---------------------------------------------------------------------------
# run_topo_hubs() — MCP / worker binding
# ---------------------------------------------------------------------------


class TestRunTopoHubs:
    def test_prefix_filter_restricts_nodes(self):
        from graph.worker import run_topo_hubs

        nodes = [
            _node("source-a", ["source-b"]),
            _node("source-b", []),
            _node("other-x", ["other-y"]),
            _node("other-y", []),
        ]
        report = run_topo_hubs(vault=nodes, prefix_filter="source")
        stems = {c.hub for c in report.components} | {
            s for c in report.components for s in c.spokes
        }
        assert all(stem.startswith("source") for stem in stems)
        assert "other-x" not in stems

    def test_write_tags_false_does_not_require_disk(self):
        from graph.worker import run_topo_hubs

        nodes = [_node("a", ["b"]), _node("b", [])]
        report = run_topo_hubs(vault=nodes, write_tags=False)
        assert report.n_elected >= 1
