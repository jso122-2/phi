"""
.cursor/hooks/formula_hook.py — formula enforcement hook plugin.

Registers FormulaGate into the MCP pre-hook chain at server startup.

The gate intercepts every formula_call invocation and blocks it if the
mathematical precondition formulas have not yet been called in this session.

Disable at runtime by setting:
    FORMULA_GATE_DISABLED=1

in the environment.  The hook still loads; it just short-circuits immediately.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_server.hooks import HookRegistry


def register_plugins(registry: "HookRegistry") -> None:
    if os.environ.get("FORMULA_GATE_DISABLED", "").strip() in ("1", "true", "yes"):
        return

    try:
        from mcp_server.formula_gate import GATE
    except Exception as exc:  # noqa: BLE001
        import sys
        print(f"[formula_hook] failed to load FormulaGate: {exc}", file=sys.stderr)
        return

    registry.register(
        name        = "formula_gate",
        description = (
            "Enforce formula-to-formula precondition ordering per session. "
            "Blocks formula_call invocations whose mathematical dependencies "
            "(e.g. F_EDGE_WEIGHT requires F_COSINE_SIMILARITY first) have not "
            "been satisfied. See config/formulas/formula_enforcement.yaml for rules."
        ),
        fn = GATE,
    )
