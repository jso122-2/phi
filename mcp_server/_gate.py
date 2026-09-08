"""
mcp_server._gate — session gate, init protocol, and requires_init decorator.

Protocol constants (PROTOCOL_VERSION, _GATE_CONTRACT_HASH) are Final so any
change is detectable by agents that verify them in their init round-trips.

SESSION_TOKEN
-------------
A short timestamp-based identifier stamped once at gate-open.  Embedded in
Notion edge notes so every Reservoir activation is traceable back to the
session that generated it.  Format: ``phi-YYYYMMDD-HHMMSSuuu`` (UTC, ms).
Exported from this module so any tool can include it without importing _state.
"""
from __future__ import annotations

import functools
import hashlib
import inspect
import threading
from datetime import datetime, timezone
from typing import Any, Final

from mcp_server.hooks import BASE_HOOK_COUNT as _BASE_HOOK_COUNT  # noqa: F401 (re-exported)
from mcp_server.hooks import HookViolation
from mcp_server.hooks import REGISTRY as _hook_registry

PROTOCOL_VERSION: Final[str] = "1.1.0"

_INIT_FREE_TOOLS: Final[frozenset[str]] = frozenset({
    "init_check", "system_status", "list_hooks", "register_hook", "dom_queue_state",
    "graph_status", "graph_clean", "graph_nest", "graph_track_state",
    "forecast_state",
    "bus_poll", "bus_status",
    "run_command", "list_commands",
})

_GATE_CONTRACT_HASH: Final[str] = hashlib.sha256(
    "|".join(sorted(_INIT_FREE_TOOLS)).encode()
).hexdigest()[:16]

# Shared validation constants imported by guard modules
_VALID_HUBS: Final[frozenset[str]] = frozenset({
    "HOME", "MATH", "CODE", "COMMANDS", "agent-context",
})
_VALID_PROPAGATE_MODES: Final[frozenset[str]] = frozenset({"local", "resonance"})
_VALID_PHI_KINDS: Final[frozenset[str]] = frozenset({
    "CLIP", "SHUFFLE_NEXT", "SHUFFLE_SEED",
    "HUB_INJECT", "SHARD_INJECT", "PROPAGATE",
    "CAIRRN_RUN", "TEMPORAL_REC", "MYCELIAL_TICK",
    "LOAD_TRACK", "HOVER_PREFETCH",
})
_SIM_X0_RANGE: Final[tuple[float, float]] = (-1000.0, 1000.0)

# ---------------------------------------------------------------------------
# Session gate state + identity token
# ---------------------------------------------------------------------------

_session_initialized: bool = False
_session_lock = threading.Lock()

# Stamped once at gate-open; never changes within a process lifetime.
# Format: phi-YYYYMMDD-HHMMSSuuu (UTC, milliseconds appended for uniqueness)
SESSION_TOKEN: str = ""


def open_gate() -> None:
    """Mark the session as initialized and stamp the SESSION_TOKEN (idempotent)."""
    global _session_initialized, SESSION_TOKEN
    with _session_lock:
        if not SESSION_TOKEN:
            now = datetime.now(timezone.utc)
            SESSION_TOKEN = now.strftime("phi-%Y%m%d-%H%M%S") + f"{now.microsecond // 1000:03d}"
        _session_initialized = True


def is_initialized() -> bool:
    """Return True if the session gate has been opened."""
    with _session_lock:
        return _session_initialized


# ---------------------------------------------------------------------------
# Pre-call hook: gate check + hook chain
# ---------------------------------------------------------------------------

def _pre_call(tool_name: str, **kwargs: Any) -> dict[str, Any] | None:
    """
    Session-init gate + pre-hook chain.

    Returns None if the call is permitted; an error dict if it must be aborted.
    """
    if tool_name not in _INIT_FREE_TOOLS and not is_initialized():
        return {
            "error": "session_not_initialized",
            "message": (
                f"'{tool_name}' requires an initialized session. "
                "Call init_check() or system_status() first to open the gate."
            ),
            "action_required": "init_check()",
        }
    try:
        _hook_registry.run(tool_name, kwargs)
    except HookViolation as exc:
        return {
            "error": "hook_violation",
            "hook": str(exc),
            "hook_chain_version": _hook_registry.version,
        }
    return None


# ---------------------------------------------------------------------------
# @requires_init decorator
# ---------------------------------------------------------------------------

def requires_init(fn: Any) -> Any:
    """
    Structural session-gate decorator.

    Apply to every substantive MCP tool. Binds call-site arguments, forwards
    them to _pre_call for gate + hook checking, and aborts with an error dict
    if either check fails.
    """
    _sig = inspect.signature(fn)

    @functools.wraps(fn)
    def _gated(*args: Any, **kwargs: Any) -> Any:
        bound = _sig.bind(*args, **kwargs)
        bound.apply_defaults()
        if err := _pre_call(fn.__name__, **bound.arguments):
            return err
        return fn(*args, **kwargs)

    return _gated


# ---------------------------------------------------------------------------
# Re-exports — backward compatibility for all existing importers
# ---------------------------------------------------------------------------
# These imports must stay at the bottom: guard modules do lazy `from
# mcp_server._gate import is_initialized` inside closures, which works
# because _gate is fully loaded by this point.

from mcp_server._env_check import _raw_init_check, _startup_init  # noqa: E402, F401
from mcp_server._context_hook import (  # noqa: E402, F401
    _register_psspps_context_hook,
    _hot_shard_query,
    _context_result,
    _context_notified,
    _context_hook_registered,
    _write_and_notify,
    _fire_direct_psspps,
    _submit_context_psspps,
)
from mcp_server._guards_graph import _register_command_dispatch  # noqa: E402, F401
