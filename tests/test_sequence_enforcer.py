"""
Tests for mcp_server.sequence_enforcer — CallLedger, SequenceRule,
SequenceEnforcer, build_enforcer, and the sequence_hook plugin.
"""
from __future__ import annotations

import os
import threading

import pytest

from mcp_server.hooks import HookRegistry, HookViolation
from mcp_server.sequence_enforcer import (
    CallLedger,
    DEFAULT_SEQUENCES,
    SequenceEnforcer,
    SequenceRule,
    build_enforcer,
)


# ---------------------------------------------------------------------------
# CallLedger
# ---------------------------------------------------------------------------

class TestCallLedger:
    def test_empty_ledger(self):
        ledger = CallLedger()
        assert ledger.has_been_called("anything") is False
        assert ledger.all_called(["a", "b"]) is False
        assert ledger.missing(["a", "b"]) == ["a", "b"]
        assert ledger.snapshot() == []

    def test_record_and_query(self):
        ledger = CallLedger()
        ledger.record("tool_a")
        assert ledger.has_been_called("tool_a") is True
        assert ledger.has_been_called("tool_b") is False

    def test_all_called(self):
        ledger = CallLedger()
        ledger.record("x")
        ledger.record("y")
        assert ledger.all_called(["x", "y"]) is True
        assert ledger.all_called(["x", "y", "z"]) is False

    def test_missing(self):
        ledger = CallLedger()
        ledger.record("x")
        assert ledger.missing(["x", "y"]) == ["y"]
        assert ledger.missing(["x"]) == []

    def test_snapshot_order(self):
        ledger = CallLedger()
        for name in ["a", "b", "c"]:
            ledger.record(name)
        names = [n for n, _ in ledger.snapshot()]
        assert names == ["a", "b", "c"]

    def test_state_structure(self):
        ledger = CallLedger()
        ledger.record("system_status")
        state = ledger.state()
        assert state["n_calls"] == 1
        assert "system_status" in state["unique_tools"]
        assert len(state["recent"]) == 1

    def test_reset(self):
        ledger = CallLedger()
        ledger.record("x")
        ledger.reset()
        assert ledger.has_been_called("x") is False

    def test_thread_safety(self):
        """Multiple threads can record concurrently without data corruption."""
        ledger = CallLedger()
        errors = []

        def worker(name: str, n: int) -> None:
            try:
                for _ in range(n):
                    ledger.record(name)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(f"t{i}", 100))
            for i in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(ledger.snapshot()) == 800


# ---------------------------------------------------------------------------
# SequenceRule
# ---------------------------------------------------------------------------

class TestSequenceRule:
    def test_basic(self):
        r = SequenceRule(tool="foo", requires=["bar"])
        assert r.tool == "foo"
        assert r.requires == ["bar"]
        assert r.message == ""

    def test_with_message(self):
        r = SequenceRule(tool="x", requires=["y"], message="call y first")
        assert r.message == "call y first"

    def test_empty_requires_raises(self):
        with pytest.raises(ValueError, match="empty requires"):
            SequenceRule(tool="x", requires=[])


# ---------------------------------------------------------------------------
# SequenceEnforcer
# ---------------------------------------------------------------------------

class TestSequenceEnforcer:
    def _simple_enforcer(self) -> SequenceEnforcer:
        """Enforcer with one rule: tool_b requires tool_a."""
        return SequenceEnforcer(
            rules=[SequenceRule(tool="tool_b", requires=["tool_a"])]
        )

    def test_no_rule_no_block(self):
        enforcer = self._simple_enforcer()
        # tool_c has no rule — should pass freely
        enforcer("tool_c", {})

    def test_prerequisite_missing_raises(self):
        enforcer = self._simple_enforcer()
        with pytest.raises(HookViolation, match="tool_b"):
            enforcer("tool_b", {})

    def test_prerequisite_satisfied(self):
        enforcer = self._simple_enforcer()
        enforcer("tool_a", {})   # satisfies prerequisite
        enforcer("tool_b", {})   # now allowed

    def test_records_in_ledger_after_pass(self):
        enforcer = self._simple_enforcer()
        enforcer("tool_a", {})
        assert enforcer.ledger.has_been_called("tool_a") is True

    def test_does_not_record_blocked_call(self):
        """Blocked calls must NOT appear in the ledger."""
        enforcer = self._simple_enforcer()
        with pytest.raises(HookViolation):
            enforcer("tool_b", {})
        # tool_b was blocked — should not appear in ledger
        assert enforcer.ledger.has_been_called("tool_b") is False

    def test_multiple_prerequisites(self):
        enforcer = SequenceEnforcer(rules=[
            SequenceRule(tool="c", requires=["a", "b"]),
        ])
        enforcer("a", {})
        with pytest.raises(HookViolation, match="'b'"):
            enforcer("c", {})
        enforcer("b", {})
        enforcer("c", {})  # now allowed

    def test_multiple_rules_for_same_tool(self):
        """All rules for the same tool must be satisfied."""
        enforcer = SequenceEnforcer(rules=[
            SequenceRule(tool="commit", requires=["status"]),
            SequenceRule(tool="commit", requires=["inspect"]),
        ])
        enforcer("status", {})
        with pytest.raises(HookViolation):
            enforcer("commit", {})
        enforcer("inspect", {})
        enforcer("commit", {})  # satisfied

    def test_state_structure(self):
        enforcer = self._simple_enforcer()
        state = enforcer.state()
        assert "ledger" in state
        assert "n_rules" in state
        assert state["n_rules"] == 1
        rule_info = state["rules"][0]
        assert rule_info["tool"] == "tool_b"
        assert rule_info["satisfied"] is False

    def test_disable_via_env(self, monkeypatch):
        monkeypatch.setenv("SPOTIFY_RIP_DISABLE_SEQUENCE_ENFORCER", "1")
        enforcer = self._simple_enforcer()
        # Should NOT raise even though tool_a hasn't been called
        enforcer("tool_b", {})
        # Even in disabled mode the call is recorded
        assert enforcer.ledger.has_been_called("tool_b") is True


# ---------------------------------------------------------------------------
# build_enforcer
# ---------------------------------------------------------------------------

class TestBuildEnforcer:
    def test_default_rules_populated(self):
        enforcer = build_enforcer()
        assert len(enforcer.rules) >= len(DEFAULT_SEQUENCES)

    def test_extra_rules_merged(self):
        extra = [SequenceRule(tool="custom_tool", requires=["init"])]
        enforcer = build_enforcer(extra_rules=extra)
        tool_names = {r.tool for r in enforcer.rules}
        assert "custom_tool" in tool_names

    def test_shared_ledger(self):
        ledger = CallLedger()
        ledger.record("system_status")
        enforcer = build_enforcer(ledger=ledger)
        # The enforcer should see the pre-seeded call
        assert enforcer.ledger.has_been_called("system_status") is True

    def test_default_graph_commit_blocked_without_status(self):
        enforcer = build_enforcer()
        with pytest.raises(HookViolation, match="graph_commit"):
            enforcer("graph_commit", {})

    def test_default_graph_commit_allowed_after_status(self):
        enforcer = build_enforcer()
        enforcer("system_status", {})
        # Should not raise
        enforcer("graph_commit", {})

    def test_harmonic_propagate_blocked_without_state(self):
        enforcer = build_enforcer()
        enforcer("system_status", {})
        with pytest.raises(HookViolation, match="harmonic_propagate"):
            enforcer("harmonic_propagate", {})

    def test_harmonic_propagate_allowed_after_state(self):
        enforcer = build_enforcer()
        enforcer("harmonic_index_state", {})
        enforcer("harmonic_propagate", {})

    def test_graph_ingest_requires_graph_status(self):
        enforcer = build_enforcer()
        enforcer("system_status", {})
        with pytest.raises(HookViolation, match="graph_ingest"):
            enforcer("graph_ingest", {})
        enforcer("graph_status", {})
        enforcer("graph_ingest", {})


# ---------------------------------------------------------------------------
# Hook registry integration
# ---------------------------------------------------------------------------

class TestRegistryIntegration:
    def test_enforcer_registers_into_registry(self):
        reg = HookRegistry()
        enforcer = build_enforcer()
        reg.register("seq", "Sequence enforcer", enforcer)
        assert reg.version == 1

    def test_enforcer_in_chain_blocks_call(self):
        reg = HookRegistry()
        enforcer = build_enforcer()
        reg.register("seq", "Sequence enforcer", enforcer)

        with pytest.raises(HookViolation):
            for hook in reg._chain:
                hook.fn("graph_commit", {})

    def test_enforcer_in_chain_passes_after_prereq(self):
        reg = HookRegistry()
        enforcer = build_enforcer()
        reg.register("seq", "Sequence enforcer", enforcer)

        # Pre-seed by calling the enforcer directly (simulates earlier calls)
        enforcer("system_status", {})
        # Now running the chain for graph_commit should pass
        for hook in reg._chain:
            hook.fn("graph_commit", {})  # no raise


# ---------------------------------------------------------------------------
# sequence_hook plugin
# ---------------------------------------------------------------------------

class TestSequenceHookPlugin:
    def _load_plugin(self, tmp_path):
        import importlib.util
        plugin_path = (
            __import__("pathlib").Path(__file__).parent.parent
            / ".cursor" / "hooks" / "sequence_hook.py"
        )
        spec   = importlib.util.spec_from_file_location("sequence_hook", plugin_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_register_plugins_adds_enforcer(self):
        module = self._load_plugin(None)
        reg = HookRegistry()
        module.register_plugins(reg)
        names = [h.name for h in reg._chain]
        assert "sequence_enforcer" in names

    def test_register_plugins_disabled_via_env(self, monkeypatch):
        monkeypatch.setenv("SPOTIFY_RIP_DISABLE_SEQUENCE_ENFORCER", "1")
        module = self._load_plugin(None)
        reg = HookRegistry()
        module.register_plugins(reg)
        names = [h.name for h in reg._chain]
        assert "sequence_enforcer" not in names

    def test_extra_notion_rule_included(self):
        module = self._load_plugin(None)
        reg = HookRegistry()
        module.register_plugins(reg)
        enforcer = next(h.fn for h in reg._chain if h.name == "sequence_enforcer")
        tools = {r.tool for r in enforcer.rules}
        assert "graph_commit" in tools
