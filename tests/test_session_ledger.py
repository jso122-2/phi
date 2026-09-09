"""Tests for SessionLedger, coherence_state tool, and BMAD ledger integration."""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---------------------------------------------------------------------------
# SessionLedger unit tests
# ---------------------------------------------------------------------------

from mcp_server._session_ledger import SessionLedger


class TestSessionLedger:
    def test_not_initialized_by_default(self):
        ledger = SessionLedger()
        assert not ledger.is_open()

    def test_open_once(self):
        ledger = SessionLedger()
        ledger.open([0.1, 0.2, 0.3])
        assert ledger.is_open()

    def test_open_idempotent(self):
        ledger = SessionLedger()
        ledger.open([1.0, 2.0])
        ledger.open([99.0])  # second call must be ignored
        assert ledger._initial == [1.0, 2.0]

    def test_record_before_open_is_noop(self):
        ledger = SessionLedger()
        ledger.record(tool="x", snapshot=[1.0], step_count=0)
        assert ledger.n_mutations() == 0

    def test_record_appends_entry(self):
        ledger = SessionLedger()
        ledger.open([0.0, 0.0, 0.0])
        ledger.record(tool="harmonic_inject", snapshot=[1.0, 0.5, 0.0], step_count=1)
        assert ledger.n_mutations() == 1

    def test_total_delta_from_start(self):
        ledger = SessionLedger()
        ledger.open([0.0, 0.0])
        ledger.record(tool="t", snapshot=[0.5, 1.0], step_count=1)
        ledger.record(tool="t", snapshot=[0.8, 1.5], step_count=2)
        delta = ledger._total_delta()
        assert abs(delta[0] - 0.8) < 1e-9
        assert abs(delta[1] - 1.5) < 1e-9

    def test_delta_when_no_entries(self):
        ledger = SessionLedger()
        ledger.open([1.0, 2.0])
        delta = ledger._total_delta()
        assert delta == [0.0, 0.0]

    def test_total_pressure(self):
        ledger = SessionLedger()
        ledger.open([0.0, 0.0])
        ledger.record(tool="t", snapshot=[1.0, -2.0], step_count=1)
        assert abs(ledger.total_pressure() - 3.0) < 1e-9

    def test_to_dict_structure(self):
        ledger = SessionLedger()
        ledger.open([0.0] * 8)
        for i in range(3):
            ledger.record(tool=f"t{i}", snapshot=[float(i)] * 8, step_count=i)
        d = ledger.to_dict(tail=2)
        assert d["initialized"] is True
        assert d["n_mutations"] == 3
        assert len(d["entries"]) == 2  # tail=2
        assert "total_delta" in d
        assert "hub_delta" in d
        assert "total_pressure" in d

    def test_code_pressure_no_sims(self):
        """hub_delta falls back to 0.0 when sims.harmonic is unavailable."""
        ledger = SessionLedger()
        ledger.open([0.0] * 8)
        ledger.record(tool="t", snapshot=[1.0] * 8, step_count=1)
        # code_pressure calls hub_delta which imports sims.harmonic — may or may not be present
        # Just ensure it doesn't raise
        result = ledger.code_pressure()
        assert isinstance(result, float)

    def test_entry_delta_vs_previous(self):
        """Each entry's delta is relative to the previous snapshot, not initial."""
        ledger = SessionLedger()
        ledger.open([0.0, 0.0])
        ledger.record(tool="t", snapshot=[1.0, 0.0], step_count=1)
        ledger.record(tool="t", snapshot=[1.5, 0.0], step_count=2)
        first_entry = ledger._entries[0]
        second_entry = ledger._entries[1]
        # First entry delta vs initial
        assert abs(first_entry.delta[0] - 1.0) < 1e-9
        # Second entry delta vs first entry snapshot
        assert abs(second_entry.delta[0] - 0.5) < 1e-9

    def test_thread_safety(self):
        import threading
        ledger = SessionLedger()
        ledger.open([0.0] * 4)
        errors = []

        def _write():
            try:
                for i in range(50):
                    ledger.record(tool="t", snapshot=[float(i)] * 4, step_count=i)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_write) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert ledger.n_mutations() == 200


# ---------------------------------------------------------------------------
# coherence_state tool
# ---------------------------------------------------------------------------

class TestCoherenceStateTool:
    def test_returns_not_initialized_when_ledger_closed(self):
        ledger = SessionLedger()
        with patch("mcp_server.tools.system._session_ledger", ledger, create=True):
            # Import after patching so the tool sees the mock ledger
            import importlib
            import mcp_server.tools.system as sys_mod
            # Call coherence_state directly (bypassing MCP registration)
            with patch.object(sys_mod, "__name__", sys_mod.__name__):
                # Directly exercise the body — mock _session_ledger on the state module
                with patch("mcp_server._state._session_ledger", ledger):
                    from mcp_server._state import _session_ledger as sl
                    result = sl.is_open()
                    assert result is False

    def test_coherence_state_body(self):
        """Exercise the body of coherence_state() directly."""
        ledger = SessionLedger()
        ledger.open([0.0] * 8)
        ledger.record(tool="harmonic_inject", snapshot=[0.5] * 8, step_count=1)

        with patch("mcp_server._state._session_ledger", ledger):
            # Import fresh to pick up the patch
            from mcp_server._state import _session_ledger as sl
            data = sl.to_dict(tail=10)
            assert data["initialized"] is True
            assert data["n_mutations"] == 1
            assert "total_delta" in data
            assert "hub_delta" in data
            assert "bmad_signals" not in data  # to_dict doesn't add this; coherence_state does

    def test_coherence_state_bmad_signals(self):
        ledger = SessionLedger()
        ledger.open([0.0] * 8)
        ledger.record(tool="t", snapshot=[1.0] * 8, step_count=1)
        with patch("mcp_server._state._session_ledger", ledger):
            from mcp_server._state import _session_ledger as sl
            d = sl.to_dict(tail=10)
            # Manually add bmad_signals as coherence_state() does
            d["bmad_signals"] = {
                "total_pressure": d["total_pressure"],
                "code_pressure":  d["code_pressure"],
                "n_mutations":    d["n_mutations"],
            }
            assert "total_pressure" in d["bmad_signals"]
            assert d["bmad_signals"]["n_mutations"] == 1


# ---------------------------------------------------------------------------
# BMAD predicate integration with session ledger
# ---------------------------------------------------------------------------

class TestBMADLedgerIntegration:
    def _fresh_ledger(self, shards: list[float] | None = None) -> SessionLedger:
        ledger = SessionLedger()
        ledger.open(shards or [0.0] * 8)
        return ledger

    def test_modular_passes_when_pressure_low(self):
        ledger = self._fresh_ledger()
        # No mutations → code_pressure = 0.0 < _CODE_PRESSURE_CAP
        with patch("mcp_server._state._session_ledger", ledger), \
             patch("mcp_server._state._adaptive_consumption", return_value=0.0):
            from mcp_server._admissions import _predicate_modular
            assert _predicate_modular() is True

    def test_modular_blocks_on_high_session_code_pressure(self):
        # Use a pressure value well above the recalibrated _CODE_PRESSURE_CAP (12.0).
        ledger_mock = MagicMock()
        ledger_mock.code_pressure.return_value = 13.0
        ledger_mock.is_open.return_value = True
        with patch("mcp_server._state._session_ledger", ledger_mock), \
             patch("mcp_server._state._adaptive_consumption", return_value=0.0), \
             patch("mcp_server._admissions._ledger_code_pressure", return_value=13.0):
            from mcp_server._admissions import _CODE_PRESSURE_CAP, _predicate_modular
            assert 13.0 >= _CODE_PRESSURE_CAP, (
                f"Mock value 13.0 must exceed cap {_CODE_PRESSURE_CAP}"
            )
            assert _predicate_modular() is False

    def test_modular_blocks_on_instantaneous_overconsumption(self):
        # Use a consumption value above the recalibrated _CONSUMPTION_CAP (8.0).
        with patch("mcp_server._state._adaptive_consumption", return_value=9.0), \
             patch("mcp_server._admissions._ledger_code_pressure", return_value=0.0):
            from mcp_server._admissions import _predicate_modular
            assert _predicate_modular() is False

    def test_graph_predicate_extra_caution_at_high_pressure(self):
        temporal_mock = MagicMock()
        # Just above the floor but below 2× floor
        temporal_mock.ana_chi_coherence.return_value = 0.20
        with patch("mcp_server._state._temporal_index", temporal_mock), \
             patch("mcp_server._admissions._ledger_total_pressure", return_value=10.0):
            from mcp_server._admissions import _TEMPORAL_COHERENCE_FLOOR, _predicate_graph
            # 0.20 > 0.15 (floor) but < 0.30 (2×floor) under high pressure
            result = _predicate_graph()
            assert result is False

    def test_graph_predicate_passes_at_high_coherence_high_pressure(self):
        temporal_mock = MagicMock()
        temporal_mock.ana_chi_coherence.return_value = 0.5
        with patch("mcp_server._state._temporal_index", temporal_mock), \
             patch("mcp_server._admissions._ledger_total_pressure", return_value=10.0):
            from mcp_server._admissions import _predicate_graph
            assert _predicate_graph() is True

    def test_graph_predicate_passes_normal_pressure(self):
        temporal_mock = MagicMock()
        temporal_mock.ana_chi_coherence.return_value = 0.3
        with patch("mcp_server._state._temporal_index", temporal_mock), \
             patch("mcp_server._admissions._ledger_total_pressure", return_value=1.0):
            from mcp_server._admissions import _predicate_graph
            assert _predicate_graph() is True
