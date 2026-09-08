"""
mcp_server.formula_gate — per-session formula enforcement contract.

Architecture
────────────
  FormulaLedger   — thread-safe, append-only log of formula calls + results
                    within a single agent session (prompt cycle).  Resets
                    when the MCP process restarts / new session begins.

  EnforcementRule — dataclass loaded from formula_enforcement.yaml;
                    maps formula_id → required predecessor formula_ids.

  FormulaGate     — callable pre-hook registered in the HookRegistry.
                    Called before every formula_call invocation; blocks
                    the call if any required predecessor formula has not
                    yet been called in this session.

Enforcement contract (per session)
────────────────────────────────────
  Mathematical dependency order is enforced:

    F_COSINE_SIMILARITY, F_JACCARD_AFFINITY   — entry points; always callable
    F_EDGE_WEIGHT                             — requires F_COSINE_SIMILARITY
    F_RAG_PRIORITY                            — requires F_COSINE_SIMILARITY
    F_PATH_COST                               — requires F_COSINE_SIMILARITY
    F_LOCAL_COHERENCE                         — requires F_COSINE_SIMILARITY
                                                       + F_JACCARD_AFFINITY

  The contract is not an access policy — it mirrors the mathematical
  structure of the formulas.  You cannot combine similarity scores into
  an edge weight before computing them.

  When a call is blocked the gate returns an error dict (same shape as
  formula_call responses) naming the missing predecessors so the agent
  knows exactly which formula to call first.

Output validation
──────────────────
  When output_finite: true in the rule, the gate validates the result
  after execution.  NaN or Inf raises FormulaContractViolation.

Session scope
─────────────
  LEDGER is a module-level singleton.  It resets on each MCP process
  start (= each agent spawn / prompt cycle).
"""
from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_ENFORCEMENT_YAML = (
    Path(__file__).parent.parent / "config" / "formulas" / "formula_enforcement.yaml"
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class FormulaContractViolation(Exception):
    """Raised when a formula result violates its output contract."""


class FormulaPreconditionError(Exception):
    """Raised when required predecessor formulas have not been called."""


# ---------------------------------------------------------------------------
# FormulaLedger — per-session record of formula calls + results
# ---------------------------------------------------------------------------

class FormulaLedger:
    """
    Thread-safe, append-only log of formula calls within one agent session.

    Records formula_id → result after each successful formula_call.
    Used by FormulaGate to check whether predecessor formulas have run.
    """

    def __init__(self) -> None:
        self._lock:    threading.Lock         = threading.Lock()
        self._called:  dict[str, float | None] = {}  # formula_id → last result

    def record(self, formula_id: str, result: float | None = None) -> None:
        """Record a successful formula call and its result."""
        with self._lock:
            self._called[formula_id] = result

    def has_been_called(self, formula_id: str) -> bool:
        """Return True if formula_id has been called in this session."""
        with self._lock:
            return formula_id in self._called

    def get_result(self, formula_id: str) -> float | None:
        """Return the last result for formula_id, or None if not called."""
        with self._lock:
            return self._called.get(formula_id)

    def missing(self, required: list[str]) -> list[str]:
        """Return the subset of required formula_ids not yet called."""
        with self._lock:
            return [fid for fid in required if fid not in self._called]

    def snapshot(self) -> dict[str, float | None]:
        """Return a copy of the current ledger state."""
        with self._lock:
            return dict(self._called)

    def reset(self) -> None:
        """Clear the ledger (called at session start or in tests)."""
        with self._lock:
            self._called.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._called)


# ---------------------------------------------------------------------------
# EnforcementRule
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EnforcementRule:
    """One row from formula_enforcement.yaml."""
    formula_id:    str
    requires:      tuple[str, ...]  = field(default_factory=tuple)
    message:       str              = ""
    output_finite: bool             = True

    def missing_from(self, ledger: FormulaLedger) -> list[str]:
        """Return predecessor formula_ids not yet in ledger."""
        return ledger.missing(list(self.requires))


# ---------------------------------------------------------------------------
# Load enforcement rules from YAML
# ---------------------------------------------------------------------------

def _load_rules(yaml_path: Path | None = None) -> dict[str, EnforcementRule]:
    """
    Parse formula_enforcement.yaml and return formula_id → EnforcementRule.

    Returns an empty dict if PyYAML is absent or the file is missing —
    the gate degrades gracefully (no enforcement) rather than crashing the
    MCP process.
    """
    path = yaml_path or _ENFORCEMENT_YAML
    if not path.exists():
        return {}
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        return {}

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:  # noqa: BLE001
        return {}

    rules: dict[str, EnforcementRule] = {}
    for row in data.get("rules", []):
        fid = row.get("formula_id", "")
        if not fid:
            continue
        rules[fid] = EnforcementRule(
            formula_id    = fid,
            requires      = tuple(row.get("requires", [])),
            message       = row.get("message", ""),
            output_finite = bool(row.get("output_finite", True)),
        )
    return rules


# ---------------------------------------------------------------------------
# FormulaGate — callable pre-hook
# ---------------------------------------------------------------------------

class FormulaGate:
    """
    Pre-hook enforcing the formula dependency contract.

    Registered into the HookRegistry under the name "formula_gate".
    Called before every MCP tool invocation; only acts on formula_call.

    On a formula_call invocation:
      1. Extracts formula_id from kwargs.
      2. Looks up the EnforcementRule for that formula_id.
      3. Checks FormulaLedger for missing predecessors.
      4. Raises FormulaPreconditionError if any are missing.

    Output validation (post-call) is handled by validate_result().
    The formula_call tool calls this explicitly after computing the result.
    """

    def __init__(
        self,
        rules:  dict[str, EnforcementRule] | None = None,
        ledger: FormulaLedger | None = None,
    ) -> None:
        self._rules  = rules  if rules  is not None else _load_rules()
        self._ledger = ledger if ledger is not None else LEDGER

    # ── pre-hook entry point ─────────────────────────────────────────────

    def __call__(self, tool_name: str, kwargs: dict[str, Any]) -> None:
        """
        Called by HookRegistry before every tool invocation.

        Only intercepts formula_call.  All other tools pass through.

        Raises FormulaPreconditionError (caught by the MCP layer and
        returned to the agent as an error response) when preconditions
        are not met.
        """
        if tool_name != "formula_call":
            return

        formula_id = kwargs.get("formula_id", "")
        if not formula_id:
            return  # let formula_call handle the missing-id error

        rule = self._rules.get(formula_id)
        if rule is None:
            return  # no rule = no restriction

        missing = rule.missing_from(self._ledger)
        if not missing:
            return  # all preconditions satisfied

        # Build a clear, agent-readable error
        missing_str = ", ".join(missing)
        hint = rule.message or (
            f"Call {missing_str} first to satisfy the mathematical "
            f"dependency of {formula_id}."
        )
        raise FormulaPreconditionError(
            f"[formula_gate] {formula_id} is blocked — required formula(s) "
            f"not yet called in this session: {missing_str}. {hint}"
        )

    # ── post-call output validation ──────────────────────────────────────

    def validate_result(self, formula_id: str, result: float) -> None:
        """
        Validate a formula result against its output contract.

        Called by formula_call after a successful eval.  Raises
        FormulaContractViolation if the result is non-finite and the rule
        requires output_finite=true.
        """
        rule = self._rules.get(formula_id)
        if rule is None:
            return
        if rule.output_finite and not math.isfinite(result):
            raise FormulaContractViolation(
                f"[formula_gate] {formula_id} produced a non-finite result "
                f"({result}). Check input values."
            )

    def record(self, formula_id: str, result: float | None = None) -> None:
        """Record a successful formula call into the ledger."""
        self._ledger.record(formula_id, result)

    # ── introspection ────────────────────────────────────────────────────

    @property
    def rules(self) -> dict[str, EnforcementRule]:
        return dict(self._rules)

    @property
    def ledger(self) -> FormulaLedger:
        return self._ledger

    def session_state(self) -> dict[str, Any]:
        """Return the current session state for agent introspection."""
        snap = self._ledger.snapshot()
        out: dict[str, Any] = {}
        for fid, rule in self._rules.items():
            missing = rule.missing_from(self._ledger)
            out[fid] = {
                "callable":      len(missing) == 0,
                "called":        fid in snap,
                "last_result":   snap.get(fid),
                "missing_first": missing,
            }
        return out


# ---------------------------------------------------------------------------
# Module singletons
# ---------------------------------------------------------------------------

LEDGER = FormulaLedger()
GATE   = FormulaGate(ledger=LEDGER)
