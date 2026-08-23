"""Pre-hook guards: graph write field completeness and command dispatch."""
from __future__ import annotations

import sys
import threading
from typing import Final

from mcp_server.hooks import HookViolation
from mcp_server.hooks import REGISTRY as _hook_registry

_CODE_CHANGE_TOOLS: Final[frozenset[str]] = frozenset({
    "graph_commit",
    "graph_ingest",
    "graph_ingest_source",
    "graph_link",
    "graph_sync_manifest",
    "graph_track_sync",
})

_code_change_guard_registered = threading.Event()
_command_dispatch_registered = threading.Event()


def _register_code_change_guard() -> None:
    """
    Register the code-change pre-hook. Idempotent.

    Mandates: session gate open for all graph write tools; non-empty
    prompt/thinking/outcome for graph_commit; non-empty source_dir for graph_ingest.
    """
    if _code_change_guard_registered.is_set():
        return

    def _code_change_guard(tool_name: str, kwargs: dict) -> None:
        if tool_name not in _CODE_CHANGE_TOOLS:
            return
        from mcp_server._gate import is_initialized
        if not is_initialized():
            raise HookViolation(
                f"{tool_name}: session gate is closed — call init_check() before "
                "making code or vault changes."
            )
        if tool_name == "graph_commit":
            for field in ("prompt", "thinking", "outcome"):
                val = kwargs.get(field, "")
                if not isinstance(val, str) or not val.strip():
                    raise HookViolation(
                        f"graph_commit: '{field}' must be a non-empty string. "
                        "All three fields (prompt, thinking, outcome) are required."
                    )
        if tool_name == "graph_ingest":
            source_dir = kwargs.get("source_dir", "")
            if not isinstance(source_dir, str) or not source_dir.strip():
                raise HookViolation(
                    "graph_ingest: 'source_dir' must be a non-empty path string."
                )

    _hook_registry.register(
        name="code_change_guard",
        description=(
            "Mandate session-gate open and field completeness for graph write / "
            "source-ingest tools."
        ),
        fn=_code_change_guard,
    )
    _code_change_guard_registered.set()


def _register_command_dispatch() -> None:
    """
    Register the slash-command pre-hook. Idempotent.

    Annotates every tool with its /slash alias; validates run_command before
    the tool body runs.
    """
    if _command_dispatch_registered.is_set():
        return

    from mcp_server.commands import (
        CommandParseError,
        parse_command,
        slash_for_tool,
    )

    def _command_dispatch(tool_name: str, kwargs: dict) -> None:
        alias = slash_for_tool(tool_name)
        if alias:
            print(
                f"[hook:command] {alias} → {tool_name}",
                file=sys.stderr,
                flush=True,
            )

        if tool_name != "run_command":
            return

        command = kwargs.get("command", "")
        if not isinstance(command, str) or not command.strip():
            raise HookViolation(
                "run_command: 'command' must be a non-empty slash string "
                "(e.g. '/do sim 1.5'). Call list_commands() for the catalog."
            )
        try:
            parsed = parse_command(command)
        except CommandParseError as exc:
            raise HookViolation(f"run_command: {exc}") from exc
        print(
            f"[hook:command] dispatch /{parsed.slash} → "
            f"{parsed.tool or parsed.context_file}",
            file=sys.stderr,
            flush=True,
        )

    _hook_registry.register(
        name="command_dispatch",
        description=(
            "Annotate every tool with its slash alias; parse and validate "
            "run_command before dispatch."
        ),
        fn=_command_dispatch,
    )
    _command_dispatch_registered.set()
