"""
.cursor/hooks/sequence_hook.py — sequence enforcer plugin.

Auto-loaded by mcp_server.hook_plugins.load_plugins() at startup.
Registers a SequenceEnforcer into the append-only hook chain so that
prerequisite tool-call ordering is enforced for every MCP session.

The enforcer's CallLedger is module-level so it persists across retriggers
as long as the server process is alive.  On server restart the ledger is
cleared automatically (new process, new session).

Extending the ruleset
---------------------
Add SequenceRule entries to the extra_rules list below or import and extend
DEFAULT_SEQUENCES directly:

    from mcp_server.sequence_enforcer import DEFAULT_SEQUENCES, SequenceRule
    DEFAULT_SEQUENCES.append(SequenceRule(tool="my_tool", requires=["init_check"]))

Disabling
---------
    SPOTIFY_RIP_DISABLE_SEQUENCE_ENFORCER=1  (env var)
"""
from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_server.hooks import HookRegistry


# Module-level singleton — shared across retriggers within the same process.
_enforcer = None


def _get_enforcer():
    global _enforcer
    if _enforcer is None:
        from mcp_server.sequence_enforcer import build_enforcer, SequenceRule
        # ── project-specific extra rules ──────────────────────────────────
        # Add any phi / Notion-aware rules here without touching the core module.
        extra: list[SequenceRule] = [
            # Notion sync must precede graph_commit if sync was triggered this session.
            # The rule only fires once sync_notion has been called; if it hasn't been
            # called at all the graph_commit goes through normally.
            SequenceRule(
                tool     = "graph_commit",
                requires = ["sync_notion"],
                message  = (
                    "sync_notion() has been called this session but the Notion→Obsidian "
                    "sync may still be running. Wait for sync_notion to return before "
                    "committing the graph so Notion nodes are included in the vault."
                ),
            ),
        ]
        _enforcer = build_enforcer(extra_rules=extra)
    return _enforcer


def register_plugins(registry: "HookRegistry") -> None:
    disabled = os.environ.get(
        "SPOTIFY_RIP_DISABLE_SEQUENCE_ENFORCER", ""
    ).strip().lower() in {"1", "true", "yes"}

    if disabled:
        print(
            "[sequence_hook] sequence enforcer disabled via env var",
            file=sys.stderr,
            flush=True,
        )
        return

    enforcer = _get_enforcer()
    registry.register(
        name="sequence_enforcer",
        description=(
            "Enforce prerequisite tool-call ordering per session. "
            "Reads CallLedger to ensure inspect-before-mutate, "
            "status-before-commit, and Notion-sync-before-graph-commit rules."
        ),
        fn=enforcer,
    )
    print(
        f"[sequence_hook] registered sequence_enforcer ({len(enforcer.rules)} rules)",
        file=sys.stderr,
        flush=True,
    )
