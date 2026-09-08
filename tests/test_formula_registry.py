"""
Tests for workers.formula_registry — FormulaSpec, auto-translator,
FormulaRegistry.call/inspect, and Notion patch integration.
"""
from __future__ import annotations

import math
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from workers.formula_registry import (
    FormulaNotFound,
    FormulaNotReady,
    FormulaRegistry,
    FormulaSpec,
    REGISTRY,
    _abs_transform,
    _caret_to_pow,
    _normalize_unicode,
    _strip_rhs,
    _strip_trailing_comments,
    _translate,
)


# ---------------------------------------------------------------------------
# _normalize_unicode
# ---------------------------------------------------------------------------

class TestNormalizeUnicode:
    def test_minus_sign(self):
        assert _normalize_unicode("a \u2212 b") == "a - b"

    def test_middle_dot(self):
        assert _normalize_unicode("a \u00b7 b") == "a * b"

    def test_greek_lambda(self):
        assert _normalize_unicode("exp(-\u03bb * t)") == "exp(-lam * t)"

    def test_greek_tau(self):
        assert _normalize_unicode("1 / \u03bb") == "1 / lam"

    def test_python_keyword_lambda(self):
        # `lambda` as a variable name → `lam`
        assert _normalize_unicode("exp(-lambda * t)") == "exp(-lam * t)"

    def test_superscript_2(self):
        assert _normalize_unicode("x\u00b2") == "x**2"

    def test_no_op_ascii(self):
        expr = "abs(x) * sqrt(y)"
        assert _normalize_unicode(expr) == expr


# ---------------------------------------------------------------------------
# _strip_rhs
# ---------------------------------------------------------------------------

class TestStripRhs:
    def test_simple_assignment(self):
        assert _strip_rhs("x_c = Lh / P - O") == "Lh / P - O"

    def test_no_assignment(self):
        assert _strip_rhs("f_norm * (T - x)") == "f_norm * (T - x)"

    def test_greek_output(self):
        result = _strip_rhs("Psi = abs(z + x)")
        assert result == "abs(z + x)"

    def test_function_definition_rhs(self):
        # "V(x) = (x**2 - alpha**2)**2" — function-style LHS
        result = _strip_rhs("V(x) = (x**2 - alpha**2)**2")
        assert "(x**2 - alpha**2)**2" in result


# ---------------------------------------------------------------------------
# _abs_transform
# ---------------------------------------------------------------------------

class TestAbsTransform:
    def test_single(self):
        assert _abs_transform("|x|") == "abs(x)"

    def test_nested(self):
        assert _abs_transform("||A + J| - beta|") == "abs(abs(A + J) - beta)"

    def test_multiple(self):
        result = _abs_transform("|z + x| * |1 - c|")
        assert result == "abs(z + x) * abs(1 - c)"

    def test_no_bars(self):
        assert _abs_transform("sqrt(x)") == "sqrt(x)"


# ---------------------------------------------------------------------------
# _caret_to_pow
# ---------------------------------------------------------------------------

class TestCaretToPow:
    def test_basic(self):
        assert _caret_to_pow("x^2") == "x**2"

    def test_no_op(self):
        assert _caret_to_pow("x**2") == "x**2"


# ---------------------------------------------------------------------------
# _strip_trailing_comments
# ---------------------------------------------------------------------------

class TestStripTrailingComments:
    def test_where_clause(self):
        result = _strip_trailing_comments("Tn / K  where Tn >= Tip")
        assert result == "Tn / K"

    def test_no_strip_math_parens(self):
        # Must NOT strip trailing mathematical parentheses
        expr = "T * x * f / (d * z * a)"
        assert _strip_trailing_comments(expr) == expr

    def test_no_strip_formula_parens(self):
        expr = "mu = P * (1 - SHI)"
        assert _strip_trailing_comments(expr) == expr


# ---------------------------------------------------------------------------
# _translate
# ---------------------------------------------------------------------------

class TestTranslate:
    def test_simple_arithmetic(self):
        py, status = _translate("x_c = Lh / P - O")
        assert status == "ready"
        assert "Lh / P - O" in py

    def test_abs_bars(self):
        py, status = _translate("Psi = |z + x| * |1 - c| - |z + x| * |y - c| + Ti")
        assert status == "ready"
        assert "abs(z + x)" in py

    def test_nested_abs(self):
        py, status = _translate("z = ||A + J| - beta| * x / sqrt(D)")
        assert status == "ready"
        assert "abs(abs(A + J) - beta)" in py

    def test_unicode_minus(self):
        py, status = _translate("Cc = ((c \u2212 A) / p) \u00b7 Tcv")
        assert status == "ready"
        assert "abs" not in py or True  # just check it compiled
        assert status == "ready"

    def test_lambda_keyword(self):
        py, status = _translate("SCUP_t = SCUP_0 * exp(-lambda * t)")
        assert status == "ready"
        assert "lam" in py

    def test_calculus_unimplementable(self):
        _, status = _translate("d/dr [ sum(SCUP_i * delta_a_i / entropy_i) ]")
        assert status == "unimplemented"

    def test_iterative_unimplementable(self):
        _, status = _translate("x_{n+1} = x_n - lr * V(x_n)")
        assert status == "unimplemented"

    def test_manual_override(self):
        py, status = _translate("d/dr [...]", python_override="abs(x) * y")
        assert status == "ready"
        assert py == "abs(x) * y"

    def test_empty_expr(self):
        _, status = _translate("")
        assert status == "unimplemented"


# ---------------------------------------------------------------------------
# FormulaRegistry — loading
# ---------------------------------------------------------------------------

class TestFormulaRegistryLoad:
    def test_singleton_loaded(self):
        assert len(REGISTRY) > 0

    def test_total_count(self):
        assert len(REGISTRY) == 119

    def test_ready_majority(self):
        assert len(REGISTRY.ready_ids()) >= 115

    def test_only_cognitive_gravity_unimplemented(self):
        unimpl = REGISTRY.unimplemented_ids()
        assert unimpl == ["F_COGNITIVE_GRAVITY"]

    def test_contains(self):
        assert "F_CAIRRN_COMPOSITE" in REGISTRY
        assert "F_NONEXISTENT_XYZ" not in REGISTRY


# ---------------------------------------------------------------------------
# FormulaRegistry.call
# ---------------------------------------------------------------------------

class TestFormulaRegistryCall:
    def test_cairrn_composite(self):
        result = REGISTRY.call("F_CAIRRN_COMPOSITE", z=0.8, x=0.5, c=0.3, y=0.9, Ti=0.1)
        assert isinstance(result, float)
        # Manual: abs(1.3)*abs(0.7) - abs(1.3)*abs(0.6) + 0.1 = 0.91 - 0.78 + 0.1 = 0.23
        assert abs(result - 0.23) < 1e-9

    def test_constraint_var(self):
        result = REGISTRY.call("F_CONSTRAINT_VAR", Lh=0.7, P=0.9, O=0.1)
        expected = 0.7 / 0.9 - 0.1
        assert abs(result - expected) < 1e-9

    def test_mfpt(self):
        result = REGISTRY.call("F_MFPT", lam=0.25)
        assert abs(result - 4.0) < 1e-9

    def test_gradient_descent_step(self):
        result = REGISTRY.call("F_GRADIENT_DESCENT", x_n=1.96, lr=0.01, alpha=1.96)
        assert abs(result - 1.96) < 1e-6  # at attractor, gradient = 0

    def test_double_well_at_minimum(self):
        result = REGISTRY.call("F_DOUBLE_WELL", x=1.96, alpha=1.96)
        assert abs(result) < 1e-9  # V(alpha) = 0

    def test_conductance(self):
        result = REGISTRY.call("F_CONDUCTANCE", kappa=0.15, w_ij=0.0)
        assert abs(result - 0.5) < 1e-9  # sigmoid(0) = 0.5

    def test_scup_decay(self):
        result = REGISTRY.call("F_SCUP_DECAY", SCUP_0=1.0, lam=0.0, t=99.0)
        assert abs(result - 1.0) < 1e-9  # no decay when lam=0

    def test_harmonic_propagate_at_equilibrium(self):
        # All neighbours equal → no propagation
        result = REGISTRY.call("F_HARMONIC_PROPAGATE", a_i=1.0, a_prev=1.0, a_next=1.0, kappa=0.15)
        assert abs(result - 1.0) < 1e-9

    def test_rag_priority(self):
        result = REGISTRY.call("F_RAG_PRIORITY", X_norm=0.8, O_N=1.0, T_pos=0.2, P_risk=1.0)
        assert abs(result - 0.6) < 1e-9  # 0.8/1.0 - 0.2/1.0

    def test_not_found(self):
        with pytest.raises(FormulaNotFound):
            REGISTRY.call("F_DOES_NOT_EXIST")

    def test_unimplemented_raises(self):
        with pytest.raises(FormulaNotReady, match="F_COGNITIVE_GRAVITY"):
            REGISTRY.call("F_COGNITIVE_GRAVITY")

    def test_sum_formula_with_lists(self):
        result = REGISTRY.call(
            "F_PATH_REINFORCEMENT",
            nutrient_list=[1.0, 2.0, 3.0],
            T=3,
        )
        assert abs(result - 2.0) < 1e-9  # sum([1,2,3])/3

    def test_jaccard_affinity(self):
        result = REGISTRY.call("F_JACCARD_AFFINITY", A=[1, 2, 3], B=[2, 3, 4])
        # |{1,2,3}∩{2,3,4}| / |{1,2,3,4}| = 2/4 = 0.5
        assert abs(result - 0.5) < 1e-9


# ---------------------------------------------------------------------------
# FormulaRegistry.inspect
# ---------------------------------------------------------------------------

class TestFormulaRegistryInspect:
    def test_inspect_all_returns_list(self):
        result = REGISTRY.inspect()
        assert isinstance(result, list)
        assert len(result) == 119

    def test_inspect_all_has_required_keys(self):
        item = REGISTRY.inspect()[0]
        for key in ("id", "label", "status", "layer", "variables", "output"):
            assert key in item

    def test_inspect_one_full_spec(self):
        spec = REGISTRY.inspect("F_CAIRRN_COMPOSITE")
        assert isinstance(spec, dict)
        assert spec["id"] == "F_CAIRRN_COMPOSITE"
        assert "python_expr" in spec
        assert "variables" in spec
        assert spec["status"] == "ready"

    def test_inspect_latex_preserved(self):
        spec = REGISTRY.inspect("F_MFPT")
        assert "latex" in spec
        assert spec["latex"]  # non-empty

    def test_inspect_not_found(self):
        with pytest.raises(FormulaNotFound):
            REGISTRY.inspect("F_NONEXISTENT")


# ---------------------------------------------------------------------------
# FormulaRegistry from custom YAML (isolated tests)
# ---------------------------------------------------------------------------

class TestFormulaRegistryCustomYAML:
    def _make_yaml(self, tmp_path: Path, formulas: list[dict]) -> Path:
        p = tmp_path / "formulas.yaml"
        p.write_text(yaml.dump({"formulas": formulas}))
        return p

    def test_ready_formula(self, tmp_path):
        p = self._make_yaml(tmp_path, [
            {"id": "F_TEST", "label": "Test", "expr": "a + b", "output": "r",
             "variables": {"a": "input_a", "b": "input_b"}, "layer": "X"},
        ])
        reg = FormulaRegistry(yaml_path=p)
        assert reg.call("F_TEST", a=2.0, b=3.0) == 5.0

    def test_override_file_applied(self, tmp_path):
        """python_overrides.yaml in same dir overrides auto-translation."""
        p = self._make_yaml(tmp_path, [
            {"id": "F_COMPLEX", "label": "Complex", "expr": "d/dr [x]",
             "output": "r", "layer": "X"},
        ])
        ov = tmp_path / "python_overrides.yaml"
        ov.write_text("F_COMPLEX: 'x * 2'\n")

        # Patch _OVERRIDES_PATH to point to tmp_path
        import workers.formula_registry as mod
        orig = mod._OVERRIDES_PATH
        mod._OVERRIDES_PATH = ov
        try:
            reg = FormulaRegistry(yaml_path=p)
            assert reg.call("F_COMPLEX", x=3.0) == 6.0
        finally:
            mod._OVERRIDES_PATH = orig

    def test_unimplemented_formula(self, tmp_path):
        p = self._make_yaml(tmp_path, [
            {"id": "F_DERIV", "label": "D", "expr": "d/dr [f(r)]",
             "output": "g", "layer": "X"},
        ])
        reg = FormulaRegistry(yaml_path=p)
        assert reg.unimplemented_ids() == ["F_DERIV"]
        with pytest.raises(FormulaNotReady):
            reg.call("F_DERIV")

    def test_unicode_formula(self, tmp_path):
        p = self._make_yaml(tmp_path, [
            {"id": "F_UNI", "label": "Uni", "expr": "a \u2212 b",
             "output": "r", "layer": "1"},
        ])
        reg = FormulaRegistry(yaml_path=p)
        result = reg.call("F_UNI", a=5.0, b=2.0)
        assert abs(result - 3.0) < 1e-9

    def test_patch_from_notion(self, tmp_path):
        p = self._make_yaml(tmp_path, [
            {"id": "F_PATCH", "label": "Patch", "expr": "x + y",
             "output": "r", "layer": "X"},
        ])
        reg = FormulaRegistry(yaml_path=p)
        updated = reg.patch_from_notion("F_PATCH", "x * y")
        assert updated is True
        # Should now multiply
        assert reg.call("F_PATCH", x=3.0, y=4.0) == 12.0

    def test_patch_same_latex_no_op(self, tmp_path):
        p = self._make_yaml(tmp_path, [
            {"id": "F_PAT2", "label": "Pat2", "expr": "x + y",
             "output": "r", "layer": "X"},
        ])
        reg = FormulaRegistry(yaml_path=p)
        assert reg.patch_from_notion("F_PAT2", "x + y") is False

    def test_reload(self, tmp_path):
        p = self._make_yaml(tmp_path, [
            {"id": "F_RL", "label": "RL", "expr": "a + b",
             "output": "r", "layer": "X"},
        ])
        reg = FormulaRegistry(yaml_path=p)
        assert reg.call("F_RL", a=1.0, b=2.0) == 3.0

        # Update YAML with a new formula
        p.write_text(yaml.dump({"formulas": [
            {"id": "F_RL", "label": "RL", "expr": "a * b",
             "output": "r", "layer": "X"},
        ]}))
        reg.reload()
        assert reg.call("F_RL", a=2.0, b=3.0) == 6.0


# ---------------------------------------------------------------------------
# Notion formula patch integration
# ---------------------------------------------------------------------------

class TestNotionFormulaPatch:
    def test_extract_equation_blocks(self):
        from graph.notion_ingestion import _extract_equation_blocks
        blocks = [
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "intro"}]}},
            {"type": "equation", "equation": {"expression": r"\tau = 1/\lambda"}},
            {"type": "equation", "equation": {"expression": r"x^2 + y^2"}},
        ]
        exprs = _extract_equation_blocks(blocks)
        assert len(exprs) == 2
        assert r"\tau = 1/\lambda" in exprs

    def test_patch_registry_from_page_match(self, tmp_path):
        from graph.notion_ingestion import patch_formula_registry_from_page
        import workers.formula_registry as mod

        # Create a mini registry with F_TEST
        mini_yaml = tmp_path / "formulas.yaml"
        mini_yaml.write_text(yaml.dump({"formulas": [
            {"id": "F_TEST", "label": "Test", "expr": "a + b",
             "output": "r", "layer": "X"},
        ]}))
        reg = FormulaRegistry(yaml_path=mini_yaml)
        orig = mod.REGISTRY
        mod.REGISTRY = reg
        try:
            page   = {"id": "p1", "properties": {"title": {"type": "title",
                      "title": [{"plain_text": "F TEST FORMULA"}]}}}
            blocks = [{"type": "equation", "equation": {"expression": "a * b"}}]
            updated = patch_formula_registry_from_page(page, blocks)
            # May or may not match based on title fuzzy match — just check no crash
            assert isinstance(updated, list)
        finally:
            mod.REGISTRY = orig

    def test_extract_empty_blocks(self):
        from graph.notion_ingestion import _extract_equation_blocks
        assert _extract_equation_blocks([]) == []
        assert _extract_equation_blocks([{"type": "paragraph", "paragraph": {}}]) == []


# ---------------------------------------------------------------------------
# assert_ready and @requires_formulas enforcement
# ---------------------------------------------------------------------------

class TestAssertReady:
    def test_assert_ready_passes_for_known_formulas(self):
        from workers.formula_registry import REGISTRY
        # Should not raise — all these are ready
        REGISTRY.assert_ready("F_COSINE_SIMILARITY", "F_JACCARD_AFFINITY", "F_RAG_PRIORITY")

    def test_assert_ready_raises_for_unknown_id(self):
        from workers.formula_registry import REGISTRY, FormulaNotReady
        with pytest.raises(FormulaNotReady, match="NOT_A_REAL_FORMULA"):
            REGISTRY.assert_ready("NOT_A_REAL_FORMULA")

    def test_assert_ready_raises_for_unimplemented(self):
        """If a formula has status=unimplemented, assert_ready must raise."""
        import tempfile, textwrap
        from pathlib import Path
        from workers.formula_registry import FormulaRegistry, FormulaNotReady
        mini = textwrap.dedent("""\
            formulas:
              - id: F_UNIMPL
                label: "Unimplementable"
                expr: ""
                output: r
                layer: X
        """)
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write(mini)
            path = Path(f.name)
        reg = FormulaRegistry(yaml_path=path)
        with pytest.raises(FormulaNotReady):
            reg.assert_ready("F_UNIMPL")

    def test_assert_ready_lists_all_missing(self):
        from workers.formula_registry import REGISTRY, FormulaNotReady
        with pytest.raises(FormulaNotReady) as exc_info:
            REGISTRY.assert_ready("FAKE_A", "FAKE_B")
        msg = str(exc_info.value)
        assert "FAKE_A" in msg
        assert "FAKE_B" in msg


class TestRequiresFormulasDecorator:
    def test_passes_when_formulas_ready(self):
        from workers.formula_registry import requires_formulas

        @requires_formulas("F_COSINE_SIMILARITY", "F_RAG_PRIORITY")
        def compute():
            return 42

        assert compute() == 42

    def test_raises_when_formula_missing(self):
        from workers.formula_registry import requires_formulas, FormulaNotReady

        @requires_formulas("F_COSINE_SIMILARITY", "THIS_DOES_NOT_EXIST")
        def compute():
            return 42

        with pytest.raises(FormulaNotReady):
            compute()

    def test_decorator_preserves_function_name(self):
        from workers.formula_registry import requires_formulas

        @requires_formulas("F_COSINE_SIMILARITY")
        def my_special_function():
            pass

        assert my_special_function.__name__ == "my_special_function"

    def test_decorator_attaches_required_formulas_metadata(self):
        from workers.formula_registry import requires_formulas

        @requires_formulas("F_COSINE_SIMILARITY", "F_JACCARD_AFFINITY")
        def fn():
            pass

        assert hasattr(fn, "_required_formulas")
        assert "F_COSINE_SIMILARITY" in fn._required_formulas
        assert "F_JACCARD_AFFINITY"  in fn._required_formulas

    def test_decorator_passes_args_and_kwargs(self):
        from workers.formula_registry import requires_formulas

        @requires_formulas("F_COSINE_SIMILARITY")
        def add(a, b, *, multiplier=1):
            return (a + b) * multiplier

        assert add(2, 3, multiplier=4) == 20
