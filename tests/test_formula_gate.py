"""
Tests for mcp_server.formula_gate — FormulaLedger, EnforcementRule, FormulaGate.
"""
from __future__ import annotations

import math
import threading
import textwrap
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_server.formula_gate import (
    FormulaLedger,
    EnforcementRule,
    FormulaGate,
    FormulaContractViolation,
    FormulaPreconditionError,
    LEDGER,
    GATE,
    _load_rules,
)


# ---------------------------------------------------------------------------
# FormulaLedger
# ---------------------------------------------------------------------------

class TestFormulaLedger:
    def test_empty_on_init(self):
        ledger = FormulaLedger()
        assert len(ledger) == 0

    def test_record_and_has_been_called(self):
        ledger = FormulaLedger()
        ledger.record("F_COSINE_SIMILARITY", 0.8)
        assert ledger.has_been_called("F_COSINE_SIMILARITY")
        assert not ledger.has_been_called("F_JACCARD_AFFINITY")

    def test_record_without_result(self):
        ledger = FormulaLedger()
        ledger.record("F_PATH_COST")
        assert ledger.has_been_called("F_PATH_COST")
        assert ledger.get_result("F_PATH_COST") is None

    def test_get_result_returns_value(self):
        ledger = FormulaLedger()
        ledger.record("F_EDGE_WEIGHT", 0.72)
        assert abs(ledger.get_result("F_EDGE_WEIGHT") - 0.72) < 1e-9

    def test_get_result_missing_returns_none(self):
        ledger = FormulaLedger()
        assert ledger.get_result("DOES_NOT_EXIST") is None

    def test_missing_returns_uncalled(self):
        ledger = FormulaLedger()
        ledger.record("F_COSINE_SIMILARITY", 1.0)
        missing = ledger.missing(["F_COSINE_SIMILARITY", "F_JACCARD_AFFINITY"])
        assert missing == ["F_JACCARD_AFFINITY"]

    def test_missing_all_uncalled(self):
        ledger = FormulaLedger()
        missing = ledger.missing(["F_A", "F_B"])
        assert set(missing) == {"F_A", "F_B"}

    def test_missing_none_when_all_called(self):
        ledger = FormulaLedger()
        ledger.record("F_A")
        ledger.record("F_B")
        assert ledger.missing(["F_A", "F_B"]) == []

    def test_snapshot(self):
        ledger = FormulaLedger()
        ledger.record("F_X", 3.14)
        snap = ledger.snapshot()
        assert snap["F_X"] == pytest.approx(3.14)
        # snapshot is a copy
        snap["F_X"] = 0.0
        assert ledger.get_result("F_X") == pytest.approx(3.14)

    def test_reset(self):
        ledger = FormulaLedger()
        ledger.record("F_COSINE_SIMILARITY", 0.9)
        ledger.reset()
        assert len(ledger) == 0
        assert not ledger.has_been_called("F_COSINE_SIMILARITY")

    def test_thread_safety(self):
        ledger = FormulaLedger()
        errors = []

        def writer(fid):
            try:
                for _ in range(100):
                    ledger.record(fid, 1.0)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(f"F_{i}",)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert len(ledger) == 8


# ---------------------------------------------------------------------------
# EnforcementRule
# ---------------------------------------------------------------------------

class TestEnforcementRule:
    def test_no_requirements(self):
        rule = EnforcementRule(formula_id="F_COSINE_SIMILARITY", requires=())
        ledger = FormulaLedger()
        assert rule.missing_from(ledger) == []

    def test_missing_predecessor(self):
        rule = EnforcementRule(
            formula_id="F_EDGE_WEIGHT",
            requires=("F_COSINE_SIMILARITY",),
        )
        ledger = FormulaLedger()
        assert rule.missing_from(ledger) == ["F_COSINE_SIMILARITY"]

    def test_satisfied_predecessor(self):
        rule = EnforcementRule(
            formula_id="F_EDGE_WEIGHT",
            requires=("F_COSINE_SIMILARITY",),
        )
        ledger = FormulaLedger()
        ledger.record("F_COSINE_SIMILARITY", 0.8)
        assert rule.missing_from(ledger) == []

    def test_partial_requirements(self):
        rule = EnforcementRule(
            formula_id="F_LOCAL_COHERENCE",
            requires=("F_COSINE_SIMILARITY", "F_JACCARD_AFFINITY"),
        )
        ledger = FormulaLedger()
        ledger.record("F_COSINE_SIMILARITY", 0.7)
        missing = rule.missing_from(ledger)
        assert missing == ["F_JACCARD_AFFINITY"]


# ---------------------------------------------------------------------------
# _load_rules from YAML
# ---------------------------------------------------------------------------

class TestLoadRules:
    def test_loads_real_yaml(self):
        rules = _load_rules()
        assert "F_COSINE_SIMILARITY" in rules
        assert "F_EDGE_WEIGHT"       in rules
        assert "F_RAG_PRIORITY"      in rules
        assert "F_PATH_COST"         in rules
        assert "F_LOCAL_COHERENCE"   in rules

    def test_entry_points_have_no_requirements(self):
        rules = _load_rules()
        assert rules["F_COSINE_SIMILARITY"].requires == ()
        assert rules["F_JACCARD_AFFINITY"].requires  == ()

    def test_edge_weight_requires_cosine(self):
        rules = _load_rules()
        assert "F_COSINE_SIMILARITY" in rules["F_EDGE_WEIGHT"].requires

    def test_local_coherence_requires_both(self):
        rules = _load_rules()
        reqs = rules["F_LOCAL_COHERENCE"].requires
        assert "F_COSINE_SIMILARITY" in reqs
        assert "F_JACCARD_AFFINITY"  in reqs

    def test_missing_yaml_returns_empty(self):
        rules = _load_rules(Path("/nonexistent/formula_enforcement.yaml"))
        assert rules == {}

    def test_custom_yaml(self):
        yaml_text = textwrap.dedent("""\
            rules:
              - formula_id: F_A
                requires: []
                message: ""
                output_finite: true
              - formula_id: F_B
                requires: [F_A]
                message: "call F_A first"
                output_finite: true
        """)
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write(yaml_text)
            path = Path(f.name)
        rules = _load_rules(path)
        assert "F_A" in rules
        assert "F_B" in rules
        assert rules["F_B"].requires == ("F_A",)
        assert rules["F_B"].message == "call F_A first"


# ---------------------------------------------------------------------------
# FormulaGate — pre-hook behaviour
# ---------------------------------------------------------------------------

class TestFormulaGate:
    def _gate(self):
        """Fresh gate with the real enforcement rules and a clean ledger."""
        ledger = FormulaLedger()
        gate   = FormulaGate(rules=_load_rules(), ledger=ledger)
        return gate, ledger

    # ── pass-through for non-formula_call tools ──────────────────────────

    def test_non_formula_call_passes(self):
        gate, _ = self._gate()
        gate("graph_commit", {"anything": 1})  # must not raise

    def test_unknown_tool_passes(self):
        gate, _ = self._gate()
        gate("totally_unknown_tool", {})  # must not raise

    # ── formula_call with entry points (no preconditions) ────────────────

    def test_cosine_callable_without_preconditions(self):
        gate, _ = self._gate()
        gate("formula_call", {"formula_id": "F_COSINE_SIMILARITY"})  # no raise

    def test_jaccard_callable_without_preconditions(self):
        gate, _ = self._gate()
        gate("formula_call", {"formula_id": "F_JACCARD_AFFINITY"})  # no raise

    # ── formula_call with unsatisfied preconditions ───────────────────────

    def test_edge_weight_blocked_without_cosine(self):
        gate, _ = self._gate()
        with pytest.raises(FormulaPreconditionError) as exc_info:
            gate("formula_call", {"formula_id": "F_EDGE_WEIGHT"})
        assert "F_COSINE_SIMILARITY" in str(exc_info.value)

    def test_rag_priority_blocked_without_cosine(self):
        gate, _ = self._gate()
        with pytest.raises(FormulaPreconditionError):
            gate("formula_call", {"formula_id": "F_RAG_PRIORITY"})

    def test_path_cost_blocked_without_cosine(self):
        gate, _ = self._gate()
        with pytest.raises(FormulaPreconditionError):
            gate("formula_call", {"formula_id": "F_PATH_COST"})

    def test_local_coherence_blocked_without_both(self):
        gate, ledger = self._gate()
        ledger.record("F_COSINE_SIMILARITY", 0.8)
        with pytest.raises(FormulaPreconditionError) as exc_info:
            gate("formula_call", {"formula_id": "F_LOCAL_COHERENCE"})
        assert "F_JACCARD_AFFINITY" in str(exc_info.value)

    def test_local_coherence_blocked_without_cosine(self):
        gate, ledger = self._gate()
        ledger.record("F_JACCARD_AFFINITY", 0.5)
        with pytest.raises(FormulaPreconditionError) as exc_info:
            gate("formula_call", {"formula_id": "F_LOCAL_COHERENCE"})
        assert "F_COSINE_SIMILARITY" in str(exc_info.value)

    # ── formula_call after satisfying preconditions ───────────────────────

    def test_edge_weight_allowed_after_cosine(self):
        gate, ledger = self._gate()
        ledger.record("F_COSINE_SIMILARITY", 1.0)
        gate("formula_call", {"formula_id": "F_EDGE_WEIGHT"})  # no raise

    def test_rag_priority_allowed_after_cosine(self):
        gate, ledger = self._gate()
        ledger.record("F_COSINE_SIMILARITY", 0.9)
        gate("formula_call", {"formula_id": "F_RAG_PRIORITY"})  # no raise

    def test_path_cost_allowed_after_cosine(self):
        gate, ledger = self._gate()
        ledger.record("F_COSINE_SIMILARITY", 0.6)
        gate("formula_call", {"formula_id": "F_PATH_COST"})  # no raise

    def test_local_coherence_allowed_after_both(self):
        gate, ledger = self._gate()
        ledger.record("F_COSINE_SIMILARITY", 0.8)
        ledger.record("F_JACCARD_AFFINITY", 0.4)
        gate("formula_call", {"formula_id": "F_LOCAL_COHERENCE"})  # no raise

    # ── unknown formula_id passes (no rule = no restriction) ─────────────

    def test_unknown_formula_id_passes(self):
        gate, _ = self._gate()
        gate("formula_call", {"formula_id": "F_NOT_IN_CONTRACT"})  # no raise

    def test_missing_formula_id_key_passes(self):
        gate, _ = self._gate()
        gate("formula_call", {})  # no formula_id → let formula_call handle it

    # ── error message quality ─────────────────────────────────────────────

    def test_error_names_missing_predecessors(self):
        gate, _ = self._gate()
        with pytest.raises(FormulaPreconditionError) as exc_info:
            gate("formula_call", {"formula_id": "F_LOCAL_COHERENCE"})
        msg = str(exc_info.value)
        # Both missing predecessors must be named
        assert "F_COSINE_SIMILARITY" in msg
        assert "F_JACCARD_AFFINITY"  in msg

    def test_error_includes_formula_id(self):
        gate, _ = self._gate()
        with pytest.raises(FormulaPreconditionError) as exc_info:
            gate("formula_call", {"formula_id": "F_EDGE_WEIGHT"})
        assert "F_EDGE_WEIGHT" in str(exc_info.value)


# ---------------------------------------------------------------------------
# FormulaGate — output validation
# ---------------------------------------------------------------------------

class TestFormulaGateOutputValidation:
    def _gate(self):
        ledger = FormulaLedger()
        return FormulaGate(rules=_load_rules(), ledger=ledger), ledger

    def test_finite_result_passes(self):
        gate, _ = self._gate()
        gate.validate_result("F_COSINE_SIMILARITY", 0.8)  # no raise

    def test_nan_raises(self):
        gate, _ = self._gate()
        with pytest.raises(FormulaContractViolation):
            gate.validate_result("F_COSINE_SIMILARITY", float("nan"))

    def test_inf_raises(self):
        gate, _ = self._gate()
        with pytest.raises(FormulaContractViolation):
            gate.validate_result("F_EDGE_WEIGHT", float("inf"))

    def test_neg_inf_raises(self):
        gate, _ = self._gate()
        with pytest.raises(FormulaContractViolation):
            gate.validate_result("F_RAG_PRIORITY", float("-inf"))

    def test_unknown_formula_no_validation(self):
        gate, _ = self._gate()
        gate.validate_result("F_UNKNOWN", float("nan"))  # no rule → no raise


# ---------------------------------------------------------------------------
# FormulaGate — record and session_state
# ---------------------------------------------------------------------------

class TestFormulaGateSession:
    def test_record_updates_ledger(self):
        ledger = FormulaLedger()
        gate   = FormulaGate(rules=_load_rules(), ledger=ledger)
        gate.record("F_COSINE_SIMILARITY", 0.95)
        assert ledger.has_been_called("F_COSINE_SIMILARITY")
        assert abs(ledger.get_result("F_COSINE_SIMILARITY") - 0.95) < 1e-9

    def test_session_state_empty(self):
        ledger = FormulaLedger()
        gate   = FormulaGate(rules=_load_rules(), ledger=ledger)
        state  = gate.session_state()
        for fid, info in state.items():
            assert info["called"]    is False
            assert info["last_result"] is None

    def test_session_state_after_cosine(self):
        ledger = FormulaLedger()
        gate   = FormulaGate(rules=_load_rules(), ledger=ledger)
        gate.record("F_COSINE_SIMILARITY", 0.7)
        state  = gate.session_state()

        assert state["F_COSINE_SIMILARITY"]["called"]   is True
        assert state["F_COSINE_SIMILARITY"]["callable"] is True
        # Edge weight now callable
        assert state["F_EDGE_WEIGHT"]["callable"]    is True
        assert state["F_RAG_PRIORITY"]["callable"]   is True
        assert state["F_PATH_COST"]["callable"]      is True
        # Local coherence still needs Jaccard
        assert state["F_LOCAL_COHERENCE"]["callable"] is False
        assert "F_JACCARD_AFFINITY" in state["F_LOCAL_COHERENCE"]["missing_first"]

    def test_session_state_fully_satisfied(self):
        ledger = FormulaLedger()
        gate   = FormulaGate(rules=_load_rules(), ledger=ledger)
        gate.record("F_COSINE_SIMILARITY", 0.8)
        gate.record("F_JACCARD_AFFINITY",  0.5)
        state  = gate.session_state()
        for fid, info in state.items():
            assert info["callable"] is True, f"{fid} should be callable"


# ---------------------------------------------------------------------------
# Module singletons
# ---------------------------------------------------------------------------

class TestSingletons:
    def test_ledger_is_formula_ledger(self):
        assert isinstance(LEDGER, FormulaLedger)

    def test_gate_is_formula_gate(self):
        assert isinstance(GATE, FormulaGate)

    def test_gate_uses_module_ledger(self):
        assert GATE.ledger is LEDGER

    def test_gate_has_real_rules(self):
        assert "F_COSINE_SIMILARITY" in GATE.rules
        assert "F_EDGE_WEIGHT"       in GATE.rules


# ---------------------------------------------------------------------------
# Hook plugin
# ---------------------------------------------------------------------------

class TestFormulaHookPlugin:
    def test_plugin_registers_formula_gate(self):
        from mcp_server.hooks import HookRegistry
        reg = HookRegistry()
        # Import and call the plugin
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location(
            "formula_hook",
            pathlib.Path(".cursor/hooks/formula_hook.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.register_plugins(reg)

        names = [h.name for h in reg._chain]
        assert "formula_gate" in names

    def test_plugin_skips_when_disabled(self, monkeypatch):
        monkeypatch.setenv("FORMULA_GATE_DISABLED", "1")
        from mcp_server.hooks import HookRegistry
        reg = HookRegistry()
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location(
            "formula_hook_disabled",
            pathlib.Path(".cursor/hooks/formula_hook.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.register_plugins(reg)
        names = [h.name for h in reg._chain]
        assert "formula_gate" not in names
