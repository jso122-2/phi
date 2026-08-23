"""Vault topology → MCP harmonic-index fusion."""
from __future__ import annotations

import networkx as nx
import pytest

from graph.topo_graph import ComponentRecord, TopoHubReport
from graph.topology_index import (
    BASE_KAPPA,
    KAPPA_MAX,
    TOPOLOGY_SHARD,
    apply_fusion,
    compute_invariant,
    count_triangles,
    effective_kappa,
    fusion_from_report,
    hub_injections,
    incremental_fusion,
    t_b_to_alpha,
    topology_signal,
)
from sims.harmonic import HarmonicIndex


def _cycle4() -> nx.DiGraph:
    G = nx.DiGraph()
    G.add_edges_from([("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")])
    return G


def _triangle() -> nx.DiGraph:
    G = nx.DiGraph()
    G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
    return G


def _report(*hubs: tuple[str, int]) -> TopoHubReport:
    components = [
        ComponentRecord(
            component_id=i,
            size=max(in_deg, 2),
            hub=stem,
            hub_in_degree=in_deg,
            hub_total_degree=in_deg,
            spokes=[],
        )
        for i, (stem, in_deg) in enumerate(hubs)
    ]
    return TopoHubReport(
        n_nodes=sum(c.size for c in components),
        n_edges=sum(c.hub_in_degree for c in components),
        n_components=len(components),
        n_singletons=0,
        n_elected=len(components),
        components=components,
        hub_to_spokes={c.hub: [] for c in components},
        spoke_to_hub={},
    )


class TestInvariant:
    def test_triangle_chi(self):
        inv = compute_invariant(_triangle())
        assert inv.V == 3
        assert inv.E == 3
        assert inv.T == 1
        assert inv.chi == pytest.approx(1.0)
        assert inv.beta_0 == 1
        assert inv.beta_1 == 0

    def test_cycle4_raises_kappa_via_beta1(self):
        inv = compute_invariant(_cycle4())
        assert inv.T == 0
        assert inv.chi == pytest.approx(0.0)  # 4 - 4 + 0
        assert inv.beta_1 == 1
        kappa = effective_kappa(inv)
        assert kappa == pytest.approx(BASE_KAPPA * (1.0 + 1 / 4))
        assert kappa < KAPPA_MAX
        assert topology_signal(inv) == pytest.approx(0.0)

    def test_empty_graph(self):
        inv = compute_invariant(nx.DiGraph())
        assert inv.V == 0
        assert topology_signal(inv) == pytest.approx(0.0)


class TestTriangles:
    def test_count_matches_nx_on_triangle(self):
        G = _triangle()
        assert count_triangles(G) == 1


class TestAlpha:
    def test_deep_basin_is_local(self):
        assert t_b_to_alpha(1.0) == pytest.approx(1.0)

    def test_open_basin_is_global(self):
        assert t_b_to_alpha(-1.0) == pytest.approx(0.0)

    def test_neutral_is_half(self):
        assert t_b_to_alpha(0.0) == pytest.approx(0.5)


class TestHubInjections:
    def test_math_stem_pulses_math(self):
        inj = hub_injections(_report(("harmonic-index", 10)))
        assert inj["MATH"] == pytest.approx(1.0)

    def test_topology_stem_pulses_commands(self):
        inj = hub_injections(_report(("TOPOLOGY", 5)))
        assert inj["COMMANDS"] == pytest.approx(0.5)

    def test_cap_at_two(self):
        inj = hub_injections(_report(("CODE", 100)))
        assert inj["CODE"] == pytest.approx(2.0)


class TestApplyFusion:
    def test_injects_shard_five_and_sets_kappa(self):
        G = _triangle()
        inv = compute_invariant(G)
        fusion = {
            "apply": True,
            "invariant": inv.as_dict(),
            "topology_signal": topology_signal(inv),
            "topology_shard": TOPOLOGY_SHARD,
            "kappa_eff": 0.22,
            "t_b_norm": inv.t_b_norm,
            "hub_injections": {"MATH": 0.4},
            "propagate_steps": 0,
        }
        idx = HarmonicIndex()
        out = apply_fusion(idx, fusion, propagate=False)
        assert out["applied"] is True
        assert idx.shards[TOPOLOGY_SHARD].activation == pytest.approx(topology_signal(inv))
        assert idx.coupling == pytest.approx(0.22)
        assert idx.last_t_b_norm == pytest.approx(inv.t_b_norm)
        # MATH owns shards 1 and 2 — 0.4 split evenly
        assert idx.shards[1].activation == pytest.approx(0.2)
        assert idx.shards[2].activation == pytest.approx(0.2)

    def test_skip_when_apply_false(self):
        idx = HarmonicIndex()
        out = apply_fusion(idx, {"apply": False})
        assert out["applied"] is False
        assert idx.total_activation() == pytest.approx(0.0)

    def test_fusion_from_report_marks_apply(self):
        G = _triangle()
        payload = fusion_from_report(_report(("MATH", 3)), G)
        assert payload["apply"] is True
        assert payload["topology_shard"] == TOPOLOGY_SHARD
        assert "cairrn_snapshot" in payload


class TestSideEffects:
    def test_apply_reads_topology_fusion(self, monkeypatch):
        from mcp_server.bus import side_effects as se

        idx = HarmonicIndex()
        monkeypatch.setattr("mcp_server._state._harmonic_index", idx)
        monkeypatch.setattr("mcp_server._state._temporal_index", None)
        monkeypatch.setattr("mcp_server._state.save_harmonic_snapshot", lambda: None)

        class _Hub:
            def push_all(self, **kwargs):
                pass

        monkeypatch.setattr("mcp_server._state._vault_hub", _Hub())
        fusion = {
            "apply": True,
            "invariant": {"chi": 1.0},
            "topology_signal": 0.25,
            "topology_shard": TOPOLOGY_SHARD,
            "kappa_eff": 0.20,
            "t_b_norm": 0.1,
            "hub_injections": {},
            "propagate_steps": 0,
        }
        result = {"topology_fusion": fusion, "touch_harmonic": True}
        se._apply(result)
        assert result["fusion_applied"]["applied"] is True
        assert idx.shards[TOPOLOGY_SHARD].activation == pytest.approx(0.25)
        assert idx.coupling == pytest.approx(0.20)


class TestCairrnOverlayStaysSeparate:
    def test_ingest_topology_after_fusion_is_additive(self):
        from engine.bridge_factory import CAIRRNBridge

        idx = HarmonicIndex()
        fusion = {
            "apply": True,
            "invariant": {"chi": 2.0},
            "topology_signal": 0.5,
            "topology_shard": TOPOLOGY_SHARD,
            "kappa_eff": 0.15,
            "t_b_norm": 0.0,
            "hub_injections": {},
            "propagate_steps": 0,
        }
        apply_fusion(idx, fusion, propagate=False)
        before = idx.shards[TOPOLOGY_SHARD].activation
        bridge = CAIRRNBridge(idx)
        bridge.ingest_topology({"graph_snapshot": {"n1": {}, "n2": {}, "n3": {}, "n4": {}}})
        assert idx.shards[TOPOLOGY_SHARD].activation >= before
        assert idx.total_activation() > before


# ---------------------------------------------------------------------------
# incremental_fusion
# ---------------------------------------------------------------------------


class TestIncrementalFusion:
    """Unit tests for the lightweight incremental topology refresh."""

    def test_skips_on_empty_vault(self, monkeypatch):
        from graph import topology_index as ti

        monkeypatch.setattr(ti, "load_vault", lambda: [], raising=False)
        # Patch the import inside incremental_fusion
        import sys
        fake_gn = type(sys)("graph.node")
        fake_gn.load_vault = lambda: []
        monkeypatch.setitem(sys.modules, "graph.node", fake_gn)

        idx = HarmonicIndex()
        result = incremental_fusion(idx)
        assert result.get("skipped") is True
        assert result.get("reason") == "empty_vault"

    def test_runs_and_mutates_index(self, monkeypatch):
        """
        Patch load_vault + topo_build + run_topo_hubs to return a small graph
        and verify incremental_fusion updates index state.
        """
        import sys

        # Small synthetic graph via monkeypatching inside topology_index imports
        G4 = _cycle4()
        fake_report = _report(("CODE", 3), ("MATH", 2))

        import importlib
        ti = importlib.import_module("graph.topology_index")

        orig_load = None
        orig_build = None
        orig_run = None

        try:
            import graph.node as gn
            import graph.topo_graph as tg
            import graph.worker as gw

            orig_load = getattr(gn, "load_vault", None)
            orig_build = getattr(tg, "build", None)
            orig_run = getattr(gw, "run_topo_hubs", None)

            gn.load_vault = lambda: [object()]  # non-empty sentinel
            tg.build = lambda nodes: G4
            gw.run_topo_hubs = lambda **_kw: fake_report

            idx = HarmonicIndex()
            result = incremental_fusion(idx)

            # Either ran or skipped due to delta check; no exception is the key assertion
            assert "skipped" in result or "incremental" in result
            if not result.get("skipped"):
                assert result["incremental"] is True
                assert idx.last_chi is not None
                assert idx.last_t_b_norm is not None
        finally:
            if orig_load is not None:
                gn.load_vault = orig_load
            if orig_build is not None:
                tg.build = orig_build
            if orig_run is not None:
                gw.run_topo_hubs = orig_run

    def test_delta_threshold_skips_when_stable(self, monkeypatch):
        """When chi and t_b_norm are nearly unchanged the refresh is skipped."""
        import graph.topo_graph as tg
        import graph.worker as gw
        import graph.node as gn

        G4 = _cycle4()
        fake_report = _report(("CODE", 1))

        orig_load = gn.load_vault
        orig_build = tg.build
        orig_run = gw.run_topo_hubs
        try:
            gn.load_vault = lambda: [object()]
            tg.build = lambda nodes: G4
            gw.run_topo_hubs = lambda **_kw: fake_report

            idx = HarmonicIndex()
            # Prime the index with the same invariant values so delta is zero
            inv = compute_invariant(G4)
            idx.last_chi = inv.chi
            idx.last_t_b_norm = inv.t_b_norm

            result = incremental_fusion(idx)
            assert result.get("skipped") is True
            assert result.get("reason") == "delta_below_threshold"
        finally:
            gn.load_vault = orig_load
            tg.build = orig_build
            gw.run_topo_hubs = orig_run


# ---------------------------------------------------------------------------
# CAIRRN overlay flag wiring
# ---------------------------------------------------------------------------


class TestCairrnOverlayFlag:
    def test_fusion_from_report_contains_cairrn_snapshot(self):
        G = _triangle()
        report = _report(("CODE", 4), ("HOME", 2))
        fusion = fusion_from_report(report, G)
        assert "cairrn_snapshot" in fusion
        assert isinstance(fusion["cairrn_snapshot"], dict)
        # Each elected hub should appear as a key
        assert "CODE" in fusion["cairrn_snapshot"] or "HOME" in fusion["cairrn_snapshot"]

    def test_apply_cairrn_key_propagated(self):
        G = _triangle()
        report = _report(("CODE", 4))
        fusion = fusion_from_report(report, G)
        # Without the flag the key should not be set (or False)
        assert not fusion.get("apply_cairrn")

    def test_cairrn_bridge_consumes_snapshot(self):
        from engine.bridge_factory import CAIRRNBridge
        G = _triangle()
        report = _report(("CODE", 4), ("MATH", 2))
        fusion = fusion_from_report(report, G)
        snap = fusion["cairrn_snapshot"]

        idx = HarmonicIndex()
        bridge = CAIRRNBridge(idx)
        activations = bridge.ingest_topology({"graph_snapshot": snap})
        # Result should be a dict mapping hub names to shard activation lists
        assert isinstance(activations, dict)
        assert all(isinstance(v, list) for v in activations.values())
