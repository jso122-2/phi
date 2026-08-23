"""MCP search control — index modulates PSSPPS perspective_alpha."""
from __future__ import annotations

import numpy as np
import pytest

from mcp_server.tools.search import _search_control


class TestSearchControl:
    def test_cold_index_auto_is_neutral(self):
        alpha, mod = _search_control(np.zeros(8), None)
        assert alpha == pytest.approx(0.5)
        assert mod["source"] == "index"

    def test_peaked_index_auto_is_local(self):
        acts = np.zeros(8)
        acts[3] = 4.0
        alpha, mod = _search_control(acts, None)
        assert alpha == pytest.approx(1.0, abs=1e-6)
        assert mod["peak_shard"] == 3
        assert mod["source"] == "index"

    def test_caller_override_wins(self):
        acts = np.zeros(8)
        acts[3] = 4.0
        alpha, mod = _search_control(acts, 0.2)
        assert alpha == pytest.approx(0.2)
        assert mod["source"] == "caller"
        assert mod["index_alpha"] == pytest.approx(1.0, abs=1e-6)

    def test_override_clipped_to_unit_interval(self):
        alpha, _ = _search_control(np.zeros(8), 2.5)
        assert alpha == pytest.approx(1.0)
        alpha, _ = _search_control(np.zeros(8), -1.0)
        assert alpha == pytest.approx(0.0)

    def test_topology_blend_on_cold_index(self):
        # cold index_alpha = 0.5, t_b_norm = 1 → topo_alpha = 1
        # blend = 0.5*0.5 + 0.5*1.0 = 0.75
        alpha, mod = _search_control(np.zeros(8), None, t_b_norm=1.0)
        assert alpha == pytest.approx(0.75)
        assert mod["source"] == "index+topology"
        assert mod["t_b_alpha"] == pytest.approx(1.0)

    def test_topology_open_basin_pulls_global(self):
        alpha, mod = _search_control(np.zeros(8), None, t_b_norm=-1.0)
        assert alpha == pytest.approx(0.25)
        assert mod["source"] == "index+topology"

    def test_caller_override_ignores_topology(self):
        alpha, mod = _search_control(np.zeros(8), 0.2, t_b_norm=1.0)
        assert alpha == pytest.approx(0.2)
        assert mod["source"] == "caller"
        assert mod["t_b_norm"] == pytest.approx(1.0)
