"""
mcp_server.tools.formulas — formula_call and formula_inspect MCP tools.

Exposes the FormulaRegistry as two agent-callable MCP tools:

  formula_inspect(formula_id="")  — list all formulas or describe one
  formula_call(formula_id, ...)   — evaluate a formula with variable bindings

The registry holds 119 vault formulas sourced from formula_dictionary.yaml
and python_overrides.yaml.  118/119 are callable Python; one (F_COGNITIVE_GRAVITY)
requires symbolic differentiation and is marked unimplemented.

Session flow example
--------------------
  system_status()
  formula_inspect()                              # browse the catalogue
  formula_inspect("F_CAIRRN_COMPOSITE")         # see variable names
  formula_call("F_CAIRRN_COMPOSITE",
               z=0.8, x=0.5, c=0.3, y=0.9, Ti=0.1)   # → 0.23
"""
from __future__ import annotations

from typing import Any

from mcp_server._gate import requires_init
from mcp_server._state import mcp


def _get_registry():
    """Lazy-load the registry singleton (avoids import cost at MCP startup)."""
    from workers.formula_registry import REGISTRY
    return REGISTRY


@mcp.tool()
@requires_init
def formula_inspect(formula_id: str = "") -> dict[str, Any]:
    """
    Inspect the formula catalogue.

    Call with no arguments (or formula_id="") to get a compact list of all
    119 formulas with their id, label, layer, status, and variable symbols.

    Call with a specific formula_id to get the full spec: latex expression,
    auto-translated python_expr, variable → semantic field mapping, output
    variable name, CAIRRN layer, and status ("ready" or "unimplemented").

    Parameters
    ----------
    formula_id   Formula id string (e.g. "F_CAIRRN_COMPOSITE").
                 Leave empty to list all formulas.

    Returns
    -------
    dict with:
        ok          True always.
        formula     Full spec dict (when formula_id given).
        formulas    List of compact dicts (when formula_id empty).
        n_ready     Number of callable formulas.
        n_total     Total formulas in registry.
    """
    reg = _get_registry()
    n_ready = len(reg.ready_ids())
    n_total = len(reg)

    if formula_id:
        try:
            spec = reg.inspect(formula_id)
            return {
                "ok":      True,
                "formula": spec,
                "n_ready": n_ready,
                "n_total": n_total,
            }
        except KeyError as exc:
            return {
                "ok":    False,
                "error": str(exc),
                "n_ready": n_ready,
                "n_total": n_total,
            }

    return {
        "ok":       True,
        "formulas": reg.inspect(),
        "n_ready":  n_ready,
        "n_total":  n_total,
    }


@mcp.tool()
@requires_init
def formula_call(
    formula_id: str,
    variables:  dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Evaluate a vault formula with the supplied variable bindings.

    Looks up the formula by id, substitutes the provided variable values into
    the Python expression, and returns the numeric result.

    Use formula_inspect(formula_id) first to see which variable names the
    formula expects.

    Parameters
    ----------
    formula_id   Exact formula id (e.g. "F_CAIRRN_COMPOSITE").
    variables    Dict of variable name → float value.
                 Example: {"z": 0.8, "x": 0.5, "c": 0.3, "y": 0.9, "Ti": 0.1}
                 Formulas that sum over lists accept list values:
                 {"x_list": [1.0, 2.0], "z_list": [0.5, 0.8], ...}

    Returns
    -------
    dict with:
        ok          True on success.
        result      Numeric result (float).
        formula_id  Echo of the requested id.
        python_expr The Python expression that was evaluated.
        variables   Echo of the supplied bindings.
        error       Error message on failure (ok=False).
    """
    reg = _get_registry()
    variables = variables or {}

    try:
        result = reg.call(formula_id, **variables)
        spec   = reg.inspect(formula_id)
        return {
            "ok":         True,
            "result":     result,
            "formula_id": formula_id,
            "python_expr": spec.get("python_expr", ""),
            "variables":  variables,
        }
    except KeyError as exc:
        return {
            "ok":         False,
            "error":      f"Formula not found: {exc}",
            "formula_id": formula_id,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok":         False,
            "error":      str(exc),
            "formula_id": formula_id,
            "variables":  variables,
        }
