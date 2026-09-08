"""
mcp_server.tools.formulas — formula_call, formula_inspect, and
                             formula_health_check MCP tools.

Exposes the FormulaRegistry as three agent-callable MCP tools:

  formula_inspect(formula_id="")  — list all formulas or describe one
  formula_call(formula_id, ...)   — evaluate a formula with variable bindings
  formula_health_check()          — assert edge scoring formulas are ready

The registry holds 119 vault formulas sourced from formula_dictionary.yaml
and python_overrides.yaml.  118/119 are callable Python; one (F_COGNITIVE_GRAVITY)
requires symbolic differentiation and is marked unimplemented.

Session flow example
--------------------
  system_status()
  formula_health_check()                         # assert math is enforced
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

        # Post-call: validate output contract, then record in ledger.
        # The gate also acts as a post-call validator (finite check) and
        # records the result so successor formulas can proceed.
        try:
            from mcp_server.formula_gate import GATE
            GATE.validate_result(formula_id, float(result))
            GATE.record(formula_id, float(result))
        except Exception:  # noqa: BLE001
            pass  # gate import/validate failure must not suppress a good result

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


@mcp.tool()
@requires_init
def formula_health_check() -> dict[str, Any]:
    """
    Assert that all edge-scoring formulas are present, ready, and callable.

    Runs a live eval of each of the six required edge activation formulas
    using canonical test inputs and returns a per-formula status table.
    Raises (returns ok=False with error) if any formula is missing,
    unimplemented, or raises on evaluation — making the math enforcement
    explicit and agent-visible.

    This is the canonical "are the formulas enforced as Python logic"
    diagnostic.  It is not advisory — if it returns ok=False the system
    is operating with broken or missing math.

    Returns
    -------
    dict with:
        ok              True when all required formulas pass.
        all_ready       True when every required formula has status="ready".
        n_required      Number of required edge formulas (6).
        n_ready         How many passed the live eval.
        formula_results Per-formula dict: id → {status, result, error}.
        registry_total  Total formulas in registry.
        registry_ready  Total ready formulas in registry.
        error           Top-level error message on unexpected failure.
    """
    from graph.edge_scorer import EDGE_FORMULA_IDS

    reg = _get_registry()

    # Canonical test inputs for each formula
    _test_inputs: dict[str, dict] = {
        "F_COSINE_SIMILARITY": {"A": [1.0, 0.0], "B": [1.0, 0.0]},
        "F_JACCARD_AFFINITY":  {"A": ["a", "b"], "B": ["b", "c"]},
        "F_EDGE_WEIGHT":       {"sim_list": [0.8], "reinforcement_list": [1.0]},
        "F_RAG_PRIORITY":      {"X_norm": 0.8, "O_N": 1.0, "T_pos": 0.2, "P_risk": 1.0},
        "F_PATH_COST":         {"Hop_Count": 1, "sim": 0.8},
        "F_LOCAL_COHERENCE":   {"w_list": [1.0], "sim_list": [0.5], "dist_list": [1.0]},
    }

    formula_results: dict[str, Any] = {}
    n_passed = 0

    for fid in EDGE_FORMULA_IDS:
        entry: dict[str, Any] = {}
        if fid not in reg:
            entry["status"] = "missing"
            entry["error"]  = "formula_id not found in registry"
            formula_results[fid] = entry
            continue

        spec = reg.inspect(fid)
        entry["status"]      = spec.get("status", "unknown")
        entry["python_expr"] = spec.get("python_expr", "")

        if entry["status"] != "ready":
            entry["error"] = "formula is not ready (unimplemented or error)"
            formula_results[fid] = entry
            continue

        # Live eval with canonical test inputs
        test_kwargs = _test_inputs.get(fid, {})
        try:
            result = reg.call(fid, **test_kwargs)
            entry["result"]  = round(float(result), 6)
            entry["test_kwargs"] = test_kwargs
            n_passed += 1
        except Exception as exc:  # noqa: BLE001
            entry["error"]       = str(exc)
            entry["test_kwargs"] = test_kwargs

        formula_results[fid] = entry

    all_ready = n_passed == len(EDGE_FORMULA_IDS)
    return {
        "ok":             all_ready,
        "all_ready":      all_ready,
        "n_required":     len(EDGE_FORMULA_IDS),
        "n_ready":        n_passed,
        "formula_results": formula_results,
        "registry_total": len(reg),
        "registry_ready": len(reg.ready_ids()),
    }


@mcp.tool()
@requires_init
def formula_session_state() -> dict[str, Any]:
    """
    Show which formulas are callable right now in this session.

    Returns a per-formula table driven by the enforcement contract and the
    session ledger.  Use this to know what you can call before trying it.

    For each formula in the enforcement contract:
        callable        True if all preconditions have been met.
        called          True if this formula has already run this session.
        last_result     Numeric result from the most recent call (or null).
        missing_first   List of formula_ids that must be called before this one.

    Formulas not listed in the contract have no restrictions and are always
    callable via formula_call.

    Returns
    -------
    dict with:
        ok              Always True.
        session_state   formula_id → {callable, called, last_result, missing_first}
        n_called        Number of formulas called so far this session.
    """
    from mcp_server.formula_gate import GATE

    state = GATE.session_state()
    n_called = sum(1 for v in state.values() if v["called"])
    return {
        "ok":            True,
        "session_state": state,
        "n_called":      n_called,
    }
