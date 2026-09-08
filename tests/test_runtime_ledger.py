"""Runtime ledger: tool family classification, gated enforcement, bypass detection."""
from __future__ import annotations

import threading

import pytest

from mcp_server._runtime_ledger import (
    LEDGER,
    SessionCallLedger,
    TOOL_FAMILY,
    _BYPASS_PATTERNS,
    _GATED_FAMILIES,
    _register_runtime_ledger,
)
from mcp_server.hooks import HookViolation, REGISTRY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_ledger() -> SessionCallLedger:
    return SessionCallLedger(maxlen=100)


def _get_hook_fn():
    """Return the runtime_ledger hook function from the registry."""
    for h in REGISTRY._chain:
        if h.name == "runtime_ledger":
            return h.fn
    raise RuntimeError("runtime_ledger hook not registered")


# ---------------------------------------------------------------------------
# SessionCallLedger unit tests
# ---------------------------------------------------------------------------

class TestSessionCallLedger:
    def test_record_increments_seq(self):
        ledger = _fresh_ledger()
        r1 = ledger.record("init_check", "init")
        r2 = ledger.record("find_query", "search")
        assert r1.seq == 1
        assert r2.seq == 2

    def test_record_counts_by_family(self):
        ledger = _fresh_ledger()
        ledger.record("init_check", "init")
        ledger.record("find_query", "search")
        ledger.record("psspps_query", "search")
        state = ledger.state()
        assert state["by_family"]["init"] == 1
        assert state["by_family"]["search"] == 2

    def test_violation_increments_violations_count(self):
        ledger = _fresh_ledger()
        ledger.record("find_query", "search", violation="gate closed")
        state = ledger.state()
        assert state["violations"] == 1

    def test_state_tail_limits_calls(self):
        ledger = _fresh_ledger()
        for i in range(20):
            ledger.record(f"tool_{i}", "other")
        state = ledger.state(tail=5)
        assert len(state["calls"]) == 5
        assert state["total_calls"] == 20

    def test_maxlen_ring_buffer(self):
        ledger = SessionCallLedger(maxlen=5)
        for i in range(10):
            ledger.record(f"tool_{i}", "other")
        state = ledger.state(tail=100)
        # Only the last 5 records are kept
        assert len(state["calls"]) == 5
        assert state["calls"][0]["tool"] == "tool_5"
        assert state["calls"][-1]["tool"] == "tool_9"
        # But total_calls still counts all 10
        assert state["total_calls"] == 10

    def test_concurrent_record_no_corruption(self):
        ledger = _fresh_ledger()
        errors: list[Exception] = []

        def worker():
            for _ in range(50):
                try:
                    ledger.record("init_check", "init")
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert ledger.state()["total_calls"] == 200


# ---------------------------------------------------------------------------
# TOOL_FAMILY mapping
# ---------------------------------------------------------------------------

class TestToolFamilyMapping:
    def test_canonical_search_tools_mapped(self):
        assert TOOL_FAMILY["find_query"] == "search"
        assert TOOL_FAMILY["psspps_query"] == "search"

    def test_canonical_dispatch_tools_mapped(self):
        for tool in ("phi_enqueue", "phi_step", "phi_queue", "phi_flush", "phi_watchdog"):
            assert TOOL_FAMILY[tool] == "dispatch", f"{tool} not in dispatch family"

    def test_init_tools_mapped(self):
        assert TOOL_FAMILY["init_check"] == "init"
        assert TOOL_FAMILY["system_status"] == "init"

    def test_system_tools_not_gated(self):
        for tool in ("session_audit", "list_hooks", "run_command", "bus_poll", "bus_status"):
            assert TOOL_FAMILY.get(tool) == "system", f"{tool} should be system"
            assert "system" not in _GATED_FAMILIES

    def test_gated_families_do_not_include_init_or_system(self):
        assert "init" not in _GATED_FAMILIES
        assert "system" not in _GATED_FAMILIES
        assert "other" not in _GATED_FAMILIES

    def test_search_and_dispatch_are_gated(self):
        assert "search" in _GATED_FAMILIES
        assert "dispatch" in _GATED_FAMILIES


# ---------------------------------------------------------------------------
# Hook registration
# ---------------------------------------------------------------------------

class TestHookRegistration:
    def test_runtime_ledger_hook_in_chain(self):
        _register_runtime_ledger()   # idempotent
        names = {h.name for h in REGISTRY._chain}
        assert "runtime_ledger" in names

    def test_idempotent_registration(self):
        before = len(REGISTRY._chain)
        _register_runtime_ledger()
        _register_runtime_ledger()
        after = len(REGISTRY._chain)
        assert after == before   # no duplicate added


# ---------------------------------------------------------------------------
# Hook enforcement — gated families require gate open
# ---------------------------------------------------------------------------

class TestGatedFamilyEnforcement:
    def _call_hook(self, tool_name: str, gate_open: bool, monkeypatch) -> None:
        """Call the runtime_ledger hook fn directly with the given gate state."""
        _register_runtime_ledger()
        hook_fn = _get_hook_fn()
        monkeypatch.setattr("mcp_server._gate._session_initialized", gate_open)
        hook_fn(tool_name, {})

    def test_search_blocked_when_gate_closed(self, monkeypatch):
        with pytest.raises(HookViolation, match="runtime_ledger"):
            self._call_hook("find_query", gate_open=False, monkeypatch=monkeypatch)

    def test_dispatch_blocked_when_gate_closed(self, monkeypatch):
        with pytest.raises(HookViolation, match="runtime_ledger"):
            self._call_hook("phi_enqueue", gate_open=False, monkeypatch=monkeypatch)

    def test_search_allowed_when_gate_open(self, monkeypatch):
        # Should not raise
        self._call_hook("find_query", gate_open=True, monkeypatch=monkeypatch)

    def test_dispatch_allowed_when_gate_open(self, monkeypatch):
        self._call_hook("phi_enqueue", gate_open=True, monkeypatch=monkeypatch)

    def test_init_always_allowed_gate_closed(self, monkeypatch):
        # init family is not in _GATED_FAMILIES — no gate check
        self._call_hook("init_check", gate_open=False, monkeypatch=monkeypatch)

    def test_system_always_allowed_gate_closed(self, monkeypatch):
        self._call_hook("session_audit", gate_open=False, monkeypatch=monkeypatch)

    def test_unknown_tool_allowed_gate_closed(self, monkeypatch):
        # "other" family is not gated
        self._call_hook("some_unknown_tool", gate_open=False, monkeypatch=monkeypatch)


# ---------------------------------------------------------------------------
# Bypass detection
# ---------------------------------------------------------------------------

class TestBypassDetection:
    def _call_with_command(self, command: str, monkeypatch) -> None:
        _register_runtime_ledger()
        hook_fn = _get_hook_fn()
        monkeypatch.setattr("mcp_server._gate._session_initialized", True)
        hook_fn("run_command", {"command": command})

    @pytest.mark.parametrize("pattern", list(_BYPASS_PATTERNS))
    def test_bypass_pattern_blocked(self, pattern, monkeypatch):
        with pytest.raises(HookViolation, match="runtime_ledger"):
            self._call_with_command(f"python -c 'from {pattern} import x'", monkeypatch)

    def test_legitimate_run_command_allowed(self, monkeypatch):
        # Normal slash command — no bypass pattern
        self._call_with_command("/do sim 1.5", monkeypatch)

    def test_empty_command_does_not_raise_bypass(self, monkeypatch):
        # Empty command is handled by another guard (command_dispatch), not bypass detector
        self._call_with_command("", monkeypatch)


# ---------------------------------------------------------------------------
# Ledger state after hook calls
# ---------------------------------------------------------------------------

class TestLedgerState:
    def test_violation_recorded_on_gate_blocked_call(self, monkeypatch):
        _register_runtime_ledger()
        hook_fn = _get_hook_fn()
        monkeypatch.setattr("mcp_server._gate._session_initialized", False)

        fresh = _fresh_ledger()
        import mcp_server._runtime_ledger as lm
        original = lm.LEDGER
        monkeypatch.setattr(lm, "LEDGER", fresh)

        try:
            hook_fn("find_query", {"query": "test"})
        except HookViolation:
            pass

        state = fresh.state()
        assert state["violations"] == 1
        assert state["calls"][0]["violation"] is not None

        monkeypatch.setattr(lm, "LEDGER", original)

    def test_clean_call_has_no_violation(self, monkeypatch):
        _register_runtime_ledger()
        hook_fn = _get_hook_fn()
        monkeypatch.setattr("mcp_server._gate._session_initialized", True)

        fresh = _fresh_ledger()
        import mcp_server._runtime_ledger as lm
        original = lm.LEDGER
        monkeypatch.setattr(lm, "LEDGER", fresh)

        hook_fn("find_query", {"query": "test"})

        state = fresh.state()
        assert state["violations"] == 0
        # violation key is absent when there is no violation (omitted from as_dict)
        assert "violation" not in state["calls"][0]

        monkeypatch.setattr(lm, "LEDGER", original)
