"""
mcp_server.sequence_enforcer — ordered tool-call sequence enforcement.

Adds a pre-hook that acts as a prerequisite gate: certain tools may only run
after a specified set of predecessor tools have already been called in the
current session.

Architecture
------------

  CallLedger          Thread-safe, append-only log of every tool call this
                      session (name + monotonic timestamp).

  SequenceRule        A single (tool_name → [prerequisites]) rule.
                      When the enforcer fires for ``tool_name`` it checks
                      that *all* prerequisites appear in the ledger.

  SequenceEnforcer    Callable pre-hook.  Wraps a list of SequenceRules and
                      a shared CallLedger.  Call it like any hook fn::

                          enforcer(tool_name, kwargs)

                      Records the call *after* prerequisite checks pass, so
                      the ledger only contains tools that were allowed through.

  DEFAULT_SEQUENCES   Ready-made ruleset for the phi/spotify-rip system.

  build_enforcer()    Factory — returns a SequenceEnforcer wired to a fresh
                      CallLedger and the default rules (or caller-supplied ones).

Usage
-----
Register via the hook plugin system::

    # .cursor/hooks/sequence_hook.py
    from mcp_server.sequence_enforcer import build_enforcer
    _ENFORCER = build_enforcer()

    def register_plugins(registry):
        registry.register(
            name="sequence_enforcer",
            description="Enforce prerequisite tool-call ordering per session.",
            fn=_ENFORCER,
        )

Or register directly in tests::

    from mcp_server.sequence_enforcer import build_enforcer
    from mcp_server.hooks import HookRegistry

    reg = HookRegistry()
    enforcer = build_enforcer()
    reg.register("seq", "seq", enforcer)

Disabling
---------
Set ``SPOTIFY_RIP_DISABLE_SEQUENCE_ENFORCER=1`` to bypass all sequence checks
(useful for one-shot scripts and testing).

Extending
---------
Add rules to ``DEFAULT_SEQUENCES`` or pass a custom list to ``build_enforcer``:

    from mcp_server.sequence_enforcer import SequenceRule, build_enforcer

    extra = [
        SequenceRule(
            tool="my_mutating_tool",
            requires=["system_status", "my_inspect_tool"],
            message="Run system_status then my_inspect_tool before mutating.",
        )
    ]
    enforcer = build_enforcer(extra_rules=extra)
"""
from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Final


# ---------------------------------------------------------------------------
# CallLedger
# ---------------------------------------------------------------------------

class CallLedger:
    """
    Append-only, thread-safe log of tool calls made this session.

    Only records calls that passed the full hook chain (i.e. were allowed
    through by all earlier hooks, including the sequence enforcer itself).

    Attributes
    ----------
    entries   List of (tool_name, monotonic_time) pairs in call order.
    """

    def __init__(self) -> None:
        self._entries: list[tuple[str, float]] = []
        self._called:  set[str]                = set()
        self._lock     = threading.Lock()

    def record(self, tool_name: str) -> None:
        """Append a successful tool call to the ledger."""
        t = time.monotonic()
        with self._lock:
            self._entries.append((tool_name, t))
            self._called.add(tool_name)

    def has_been_called(self, tool_name: str) -> bool:
        """Return True if ``tool_name`` appears at least once in the ledger."""
        with self._lock:
            return tool_name in self._called

    def all_called(self, tool_names: list[str]) -> bool:
        """Return True iff every name in ``tool_names`` has been called."""
        with self._lock:
            return all(n in self._called for n in tool_names)

    def missing(self, tool_names: list[str]) -> list[str]:
        """Return the subset of ``tool_names`` not yet in the ledger."""
        with self._lock:
            return [n for n in tool_names if n not in self._called]

    def snapshot(self) -> list[tuple[str, float]]:
        """Return a copy of all (tool_name, time) entries."""
        with self._lock:
            return list(self._entries)

    def state(self) -> dict[str, Any]:
        """Serialisable summary for MCP inspection."""
        with self._lock:
            return {
                "n_calls":       len(self._entries),
                "unique_tools":  sorted(self._called),
                "recent":        [
                    {"tool": t, "elapsed_s": round(time.monotonic() - ts, 3)}
                    for t, ts in self._entries[-10:]
                ],
            }

    def reset(self) -> None:
        """Clear the ledger (test helper — not called during normal operation)."""
        with self._lock:
            self._entries.clear()
            self._called.clear()


# ---------------------------------------------------------------------------
# SequenceRule
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SequenceRule:
    """
    A prerequisite rule: ``tool`` may only run after ALL ``requires`` have run.

    Attributes
    ----------
    tool     The tool whose call triggers the check.
    requires Non-empty list of tool names that must appear in the ledger first.
    message  Optional human-readable explanation surfaced in the HookViolation.
             If omitted a generic message is generated.
    """
    tool:     str
    requires: list[str]
    message:  str = ""

    def __post_init__(self) -> None:
        if not self.requires:
            raise ValueError(f"SequenceRule for {self.tool!r} has empty requires list")


# ---------------------------------------------------------------------------
# DEFAULT_SEQUENCES
# ---------------------------------------------------------------------------

DEFAULT_SEQUENCES: Final[list[SequenceRule]] = [
    # ── Read before mutate ──────────────────────────────────────────────────
    SequenceRule(
        tool     = "graph_commit",
        requires = ["system_status"],
        message  = (
            "Call system_status() first to confirm harmonic state and env health "
            "before committing to the vault graph."
        ),
    ),
    SequenceRule(
        tool     = "graph_ingest",
        requires = ["graph_status"],
        message  = (
            "Call graph_status() first to verify the vault graph is healthy "
            "before ingesting new nodes."
        ),
    ),
    SequenceRule(
        tool     = "graph_ingest_source",
        requires = ["graph_status"],
        message  = "Call graph_status() before ingesting source files.",
    ),
    SequenceRule(
        tool     = "graph_link",
        requires = ["graph_status"],
        message  = "Call graph_status() before linking nodes.",
    ),
    # ── Inspect before propagate ────────────────────────────────────────────
    SequenceRule(
        tool     = "harmonic_propagate",
        requires = ["harmonic_index_state"],
        message  = (
            "Call harmonic_index_state() to read current shard activations "
            "before propagating the harmonic index."
        ),
    ),
    SequenceRule(
        tool     = "harmonic_inject",
        requires = ["harmonic_index_state"],
        message  = "Call harmonic_index_state() before injecting into the harmonic ring.",
    ),
    SequenceRule(
        tool     = "hub_inject",
        requires = ["hub_state"],
        message  = "Call hub_state() before injecting into a hub.",
    ),
    # ── Status before reset ─────────────────────────────────────────────────
    SequenceRule(
        tool     = "harmonic_reset",
        requires = ["harmonic_index_state"],
        message  = (
            "Call harmonic_index_state() to capture the current state "
            "before resetting the harmonic index."
        ),
    ),
    # ── Notion sync before graph commit ─────────────────────────────────────
    # If notion sync is part of the session, commit *after* sync has settled.
    SequenceRule(
        tool     = "graph_commit",
        requires = ["system_status"],  # already covered above; kept for clarity
        message  = (
            "If syncing Notion→Obsidian this session, call sync_notion() before "
            "graph_commit so the vault includes the latest Notion reservoir nodes."
        ),
    ),
    # ── Simulation sanity ───────────────────────────────────────────────────
    SequenceRule(
        tool     = "sweep_attractors",
        requires = ["harmonic_index_state"],
        message  = "Call harmonic_index_state() before sweeping attractors.",
    ),
    SequenceRule(
        tool     = "ana_chi_sim",
        requires = ["harmonic_index_state"],
        message  = "Call harmonic_index_state() before running ana_chi_sim.",
    ),
]


# ---------------------------------------------------------------------------
# SequenceEnforcer (the hook callable)
# ---------------------------------------------------------------------------

class SequenceEnforcer:
    """
    Pre-hook that enforces ordered tool-call sequences.

    Maintains a ``CallLedger`` and checks each incoming call against the
    ruleset.  Records the call name in the ledger *after* all checks pass
    so the ledger reflects the observed execution order accurately.

    If a tool appears in multiple rules all rules are checked; the first
    violation aborts the call.
    """

    def __init__(
        self,
        rules:  list[SequenceRule],
        ledger: CallLedger | None = None,
    ) -> None:
        self._rules  = rules
        self._ledger = ledger or CallLedger()
        # Index rules by tool name for O(1) lookup.
        self._rule_index: dict[str, list[SequenceRule]] = {}
        for r in rules:
            self._rule_index.setdefault(r.tool, []).append(r)

    # ── Public surface ─────────────────────────────────────────────────────

    @property
    def ledger(self) -> CallLedger:
        return self._ledger

    @property
    def rules(self) -> list[SequenceRule]:
        return list(self._rules)

    def state(self) -> dict[str, Any]:
        """Serialisable snapshot (ledger + rule summary)."""
        return {
            "ledger": self._ledger.state(),
            "n_rules": len(self._rules),
            "rules": [
                {
                    "tool":     r.tool,
                    "requires": r.requires,
                    "message":  r.message,
                    "satisfied": self._ledger.all_called(r.requires),
                    "missing":   self._ledger.missing(r.requires),
                }
                for r in self._rules
            ],
        }

    # ── Hook callable ──────────────────────────────────────────────────────

    def __call__(self, tool_name: str, kwargs: dict) -> None:  # noqa: ARG002
        """
        Pre-hook entrypoint.

        Called by the HookRegistry before every tool invocation.
        Records the call in the ledger only after all sequence checks pass.
        """
        if os.environ.get("SPOTIFY_RIP_DISABLE_SEQUENCE_ENFORCER", "").strip().lower() in {
            "1", "true", "yes",
        }:
            self._ledger.record(tool_name)
            return

        violations: list[str] = []
        for rule in self._rule_index.get(tool_name, []):
            missing = self._ledger.missing(rule.requires)
            if missing:
                hint = rule.message or (
                    f"Call {', '.join(missing)} before {tool_name}."
                )
                violations.append(
                    f"missing prerequisites {missing}: {hint}"
                )

        if violations:
            from mcp_server.hooks import HookViolation
            detail = "; ".join(violations)
            raise HookViolation(
                f"sequence_enforcer: '{tool_name}' blocked — {detail}"
            )

        # Record *after* checks pass.
        self._ledger.record(tool_name)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_enforcer(
    extra_rules: list[SequenceRule] | None = None,
    ledger: CallLedger | None = None,
) -> SequenceEnforcer:
    """
    Return a SequenceEnforcer ready to register as a hook.

    Parameters
    ----------
    extra_rules  Additional rules merged with DEFAULT_SEQUENCES.
                 Duplicates (same tool + requires) are kept — the first
                 violation encountered wins.
    ledger       Shared CallLedger.  A fresh one is created if omitted.
    """
    rules = list(DEFAULT_SEQUENCES)
    if extra_rules:
        rules.extend(extra_rules)
    return SequenceEnforcer(rules=rules, ledger=ledger or CallLedger())
