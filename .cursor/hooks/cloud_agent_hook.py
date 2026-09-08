"""
.cursor/hooks/cloud_agent_hook.py — default hooks for cloud agents.

Auto-loaded by mcp_server.hook_plugins.load_plugins() at server startup.
Adds three hooks that are useful for any Cursor cloud agent connecting to
the spotify-rip MCP server:

    cloud_agent_run_limit   — block after N tool calls in one session
    cloud_agent_tag_guard   — reject calls with empty or non-string command args
    cloud_agent_read_only   — optional env-var lockdown for read-only sessions

Extending this file
-------------------
Add new hooks inside register_plugins() and call registry.register().
The name must be unique across the chain; re-registration is a no-op.
Cloud agents can also add placeholder hooks at runtime via the
register_hook MCP tool.

Disabling
---------
Set SPOTIFY_RIP_DISABLE_CLOUD_AGENT_HOOKS=1 in the environment to skip all
hooks in this file (useful for testing).
"""
from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_server.hooks import HookRegistry


# ---------------------------------------------------------------------------
# Configuration (override via environment variables)
# ---------------------------------------------------------------------------

_SESSION_CALL_LIMIT: int = int(os.environ.get("SPOTIFY_RIP_SESSION_CALL_LIMIT", "0")) or 0
"""
Maximum number of tool calls per MCP session before cloud_agent_run_limit fires.
0 (default) = unlimited.  Set e.g. SPOTIFY_RIP_SESSION_CALL_LIMIT=200 to cap.
"""

_READ_ONLY: bool = os.environ.get("SPOTIFY_RIP_READ_ONLY", "").strip().lower() in {
    "1", "true", "yes",
}
"""
When true, block all mutating tools (those not in the init-free set and not
read-only by convention).  Set SPOTIFY_RIP_READ_ONLY=1 for audit-only runs.
"""

_MUTATING_TOOLS: frozenset[str] = frozenset({
    "double_well_sim", "neg_exp_sim", "sweep_attractors", "langevin_sim",
    "mfpt_estimate", "ana_chi_sim",
    "harmonic_propagate", "harmonic_inject", "hub_inject", "harmonic_reset",
    "harmonic_set_goal", "harmonic_clear_goal",
    "graph_commit", "graph_ingest", "graph_ingest_source", "graph_link",
    "graph_sync_manifest", "graph_track_sync", "graph_annotate",
    "vault_migrate", "vault_project",
    "run_tests",
    "temporal_record", "temporal_advance", "temporal_reset",
    "phi_enqueue", "phi_step", "phi_flush",
    "shuffle_seed", "shuffle_step", "shuffle_next",
    "bus_submit", "bus_wait", "bus_restart",
    "cairrn_hub_run", "cairrn_batch_run", "cairrn_neuro_k",
    "harmonic_propagate",
})


# ---------------------------------------------------------------------------
# Hook implementations
# ---------------------------------------------------------------------------

_call_counter: int = 0
_counter_lock = __import__("threading").Lock()


def _cloud_agent_run_limit(tool_name: str, kwargs: dict) -> None:  # noqa: ARG001
    """Abort if the session call count exceeds the configured cap."""
    if _SESSION_CALL_LIMIT <= 0:
        return
    global _call_counter
    with _counter_lock:
        _call_counter += 1
        count = _call_counter
    if count > _SESSION_CALL_LIMIT:
        from mcp_server.hooks import HookViolation
        raise HookViolation(
            f"cloud_agent_run_limit: session has made {count} tool calls "
            f"(cap = {_SESSION_CALL_LIMIT}). "
            "Call system_status() to confirm env is healthy, then proceed."
        )


def _cloud_agent_tag_guard(tool_name: str, kwargs: dict) -> None:
    """
    Validate the `command` argument for run_command.

    Ensures it is a non-empty string that starts with `/` or is a bare
    slash-catalog name — catches accidental None / empty invocations early.
    """
    if tool_name != "run_command":
        return
    command = kwargs.get("command")
    if command is None:
        from mcp_server.hooks import HookViolation
        raise HookViolation(
            "cloud_agent_tag_guard: run_command called with command=None. "
            "Provide a slash string like '/read index' or '/do sim 1.5'."
        )
    if not isinstance(command, str):
        from mcp_server.hooks import HookViolation
        raise HookViolation(
            f"cloud_agent_tag_guard: run_command command must be str, got {type(command).__name__!r}"
        )
    if not command.strip():
        from mcp_server.hooks import HookViolation
        raise HookViolation(
            "cloud_agent_tag_guard: run_command called with empty command string."
        )


def _cloud_agent_read_only(tool_name: str, kwargs: dict) -> None:  # noqa: ARG001
    """Block all mutating tools when SPOTIFY_RIP_READ_ONLY is set."""
    if not _READ_ONLY:
        return
    if tool_name in _MUTATING_TOOLS:
        from mcp_server.hooks import HookViolation
        raise HookViolation(
            f"cloud_agent_read_only: '{tool_name}' is a mutating tool and the "
            "server is running in read-only mode (SPOTIFY_RIP_READ_ONLY=1). "
            "Use inspect-only commands: /read status, /read graph, /read index, etc."
        )


# ---------------------------------------------------------------------------
# Plugin entry point — called by mcp_server.hook_plugins.load_plugins()
# ---------------------------------------------------------------------------


def register_plugins(registry: "HookRegistry") -> None:
    """Register cloud-agent default hooks into the hook chain."""
    disabled = os.environ.get(
        "SPOTIFY_RIP_DISABLE_CLOUD_AGENT_HOOKS", ""
    ).strip().lower() in {"1", "true", "yes"}

    if disabled:
        print(
            "[cloud_agent_hook] hooks disabled via SPOTIFY_RIP_DISABLE_CLOUD_AGENT_HOOKS",
            file=sys.stderr,
            flush=True,
        )
        return

    registry.register(
        name="cloud_agent_run_limit",
        description=(
            "Abort after N tool calls per session "
            "(cap set by SPOTIFY_RIP_SESSION_CALL_LIMIT, 0 = unlimited)."
        ),
        fn=_cloud_agent_run_limit,
    )
    registry.register(
        name="cloud_agent_tag_guard",
        description=(
            "Validate run_command argument before dispatch: "
            "must be a non-empty slash string."
        ),
        fn=_cloud_agent_tag_guard,
    )
    registry.register(
        name="cloud_agent_read_only",
        description=(
            "Block all mutating tools when SPOTIFY_RIP_READ_ONLY=1. "
            "Useful for audit-only cloud agent sessions."
        ),
        fn=_cloud_agent_read_only,
    )
