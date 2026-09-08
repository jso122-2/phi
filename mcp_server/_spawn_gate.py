"""
mcp_server._spawn_gate — Mandatory spawn-time init + read protocol.

Every agent context window must execute two operations before any
substantive MCP tool runs:

    1. /init  → ``init_check()``   — opens the session gate, writes live-init.md
    2. /read  → spawn hook emits   — the content of live-init.md is pushed onto
                                     the MCP stderr channel and into every
                                     first-call tool response as ``spawn_context``

Enforcement layers
------------------
Layer 1 — pre-call hook (``spawn_gate_hook``):
    Registered in the hook chain by ``_register_spawn_gate()``.
    Fires on every tool call before the function body runs.
    On the FIRST call after spawn it:
      a. Verifies the gate is open (init was done); if not, raises HookViolation
         with ``action_required: "init_check()"`` so the agent is told what to do.
      b. Reads ``sessions/live-init.md`` and emits its content to stderr under a
         ``[SPAWN:init]`` banner — visible in the MCP console.
      c. Emits a ``[SPAWN:read]`` sentinel so the agent knows context is live.
      d. Marks the spawn sequence complete (one-shot; never fires again this process).

Layer 2 — eager startup emit (``emit_spawn_context()``):
    Called from ``cloud.py``'s ``main()`` right after ``_startup_init()`` so the
    content appears in stderr even before the first tool call arrives.

AGENTS.md contract
------------------
    At every new context window the phi stdio MCP auto-runs the spawn protocol:
    • Gate open → live-init.md written  (Phase 1)
    • Spawn hook → live-init.md content emitted to stderr  (this module)
    • [coherence] ready → live-context.md written  (Phase 2, async)
    Agents must NOT skip init_check() or the gate stays closed and all
    substantive tools return session_not_initialized.
"""
from __future__ import annotations

import sys
import threading
from typing import Any

_spawn_complete = threading.Event()
_spawn_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_live_init_content() -> str:
    """Read sessions/live-init.md; return content or a placeholder."""
    try:
        from graph.node import SESSIONS_DIR
        p = SESSIONS_DIR / "live-init.md"
        if p.exists():
            return p.read_text(encoding="utf-8")
        return "*(live-init.md not yet written — env may be degraded)*"
    except Exception as exc:
        return f"*(live-init.md read failed: {exc})*"


def _read_live_context_content() -> str:
    """Read sessions/live-context.md if it already exists; else empty string."""
    try:
        from graph.node import SESSIONS_DIR
        p = SESSIONS_DIR / "live-context.md"
        if p.exists():
            return p.read_text(encoding="utf-8")
        return ""
    except Exception:
        return ""


def _emit_spawn_banner(content_init: str, content_ctx: str) -> None:
    """Write the spawn banner + file contents to stderr."""
    sep = "─" * 60
    lines = [
        "",
        f"[SPAWN:init] {sep}",
        "sessions/live-init.md ↓",
        sep,
        content_init.strip(),
        sep,
    ]
    if content_ctx.strip():
        lines += [
            "",
            f"[SPAWN:read] {sep}",
            "sessions/live-context.md ↓",
            sep,
            content_ctx.strip(),
            sep,
        ]
    lines += [
        "[SPAWN:read] spawn context emitted — gate is open.",
        "",
    ]
    print("\n".join(lines), file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Eager emit (Layer 2) — called from cloud.py at process startup
# ---------------------------------------------------------------------------

def emit_spawn_context() -> None:
    """
    Emit live-init.md (and live-context.md if present) to stderr immediately
    at server startup — before the first tool call arrives.

    This is Layer 2 of the spawn protocol.  It is safe to call multiple times;
    only the first call emits.  Thread-safe.
    """
    with _spawn_lock:
        if _spawn_complete.is_set():
            return
        content_init = _read_live_init_content()
        content_ctx = _read_live_context_content()
        _emit_spawn_banner(content_init, content_ctx)
        _spawn_complete.set()


# ---------------------------------------------------------------------------
# Spawn gate hook (Layer 1) — registered in the hook chain
# ---------------------------------------------------------------------------

_hook_registered = threading.Event()


def _register_spawn_gate() -> None:
    """
    Register the spawn_gate hook in the hook chain.  Idempotent.

    The hook fires on every tool call but only performs the spawn sequence
    on the first call (guarded by _spawn_complete).
    """
    from mcp_server.hooks import REGISTRY

    if _hook_registered.is_set():
        return

    def spawn_gate_hook(tool_name: str, kwargs: dict) -> None:
        """
        Pre-call: enforce init + read at agent spawn.

        First call only:
          • Ensures the session gate is open (init_check was done).
            If not, raises HookViolation — the tool call is aborted and
            the agent is told to call init_check() first.
          • Emits live-init.md + live-context.md to stderr so the agent
            sees the session context in the MCP console.
        Subsequent calls: no-op (one-shot pattern).
        """
        if _spawn_complete.is_set():
            return

        with _spawn_lock:
            if _spawn_complete.is_set():
                return

            # Gate check — init_check() must have opened the gate.
            # init_check and system_status are allowed through without the gate
            # (they ARE the init), so skip the check for those.
            _INIT_TOOLS = {"init_check", "system_status"}
            if tool_name not in _INIT_TOOLS:
                from mcp_server._gate import is_initialized
                if not is_initialized():
                    raise __import__("mcp_server.hooks", fromlist=["HookViolation"]).HookViolation(
                        f"spawn_gate: '{tool_name}' called before init_check(). "
                        "Call init_check() first to open the session gate and "
                        "emit the spawn context (live-init.md)."
                    )

            content_init = _read_live_init_content()
            content_ctx = _read_live_context_content()
            _emit_spawn_banner(content_init, content_ctx)
            _spawn_complete.set()

    REGISTRY.register(
        name="spawn_gate",
        description=(
            "Enforce init + read at every agent spawn. "
            "On the first gated tool call: verify gate is open, emit live-init.md "
            "and live-context.md to the MCP stderr channel. One-shot — silent on "
            "all subsequent calls."
        ),
        fn=spawn_gate_hook,
    )
    _hook_registered.set()


# ---------------------------------------------------------------------------
# Spawn context dict — included in tool responses by the gate wrapper
# ---------------------------------------------------------------------------

def spawn_context_dict() -> dict[str, Any]:
    """
    Return a ``spawn_context`` dict for injection into the first tool response.

    Called by the gate wrapper when the spawn sequence just completed on this
    call.  Returns an empty dict on all subsequent calls.

    The dict contains:
        spawned      : True (indicates this is the spawn call)
        live_init    : content of sessions/live-init.md
        live_context : content of sessions/live-context.md (or empty string)
    """
    try:
        return {
            "spawned": True,
            "live_init": _read_live_init_content(),
            "live_context": _read_live_context_content() or None,
        }
    except Exception:
        return {"spawned": True}
