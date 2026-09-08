"""MCP tools: run_command, list_commands — slash-command dispatcher."""
from __future__ import annotations

import importlib
from typing import Any

from mcp_server._gate import _pre_call
from mcp_server._state import _dom_queue, mcp
from mcp_server.commands import (
    CommandParseError,
    ParsedCommand,
    alias_map,
    list_catalog,
    parse_command,
    _subs_listing,
)


def _invoke(parsed: ParsedCommand) -> dict[str, Any]:
    """Import and call the target MCP tool in-process (re-enters the pre-hook chain)."""
    if parsed.kind == "dispatcher":
        return {
            "kind": "dispatcher",
            "command": f"/{parsed.slash}",
            "description": parsed.description,
            "subcommands": parsed.kwargs.get("subcommands") or [],
            "hint": (
                f"Call run_command with /{parsed.slash} <sub> …. "
                f"/{parsed.slash} help lists every subcommand."
            ),
        }
    if parsed.kind == "workflow":
        out: dict[str, Any] = {
            "kind": "workflow",
            "command": f"/{parsed.slash}",
            "context_file": parsed.context_file,
            "description": parsed.description,
            "instruction": (
                f"Read {parsed.context_file} immediately and follow its "
                "behaviour contract for the rest of this session."
            ),
        }
        topic = parsed.kwargs.get("topic")
        if topic:
            out["topic"] = topic
        return out
    if not parsed.tool or not parsed.module:
        return {"error": "undispatchable", "command": parsed.raw}
    if parsed.tool in {"run_command", "list_commands"}:
        # Avoid recursion; list is handled by list_commands itself.
        if parsed.tool == "list_commands":
            rows = list_catalog(aliases=True)
            return {
                "kind": "mcp",
                "command": f"/{parsed.slash}",
                "tool": "list_commands",
                "n": len(rows),
                "commands": rows,
                "aliases": alias_map(),
            }
        return {"error": "recursive_dispatch", "command": parsed.raw}

    mod = importlib.import_module(parsed.module)
    fn = getattr(mod, parsed.tool)
    result = fn(**parsed.kwargs)
    if not isinstance(result, dict):
        return {
            "kind": "mcp",
            "command": f"/{parsed.slash}",
            "tool": parsed.tool,
            "result": result,
        }
    wrapped = dict(result)
    wrapped.setdefault("kind", "mcp")
    wrapped.setdefault("command", f"/{parsed.slash}")
    wrapped.setdefault("dispatched_tool", parsed.tool)
    return wrapped


@mcp.tool()
def list_commands() -> dict[str, Any]:
    """
    List every slash command the agent can run through this MCP server.

    Init-free. Source of truth: mcp_server.commands.SPECS.
    Prefer run_command(command="/…") over Shell for all of these.
    """
    with _dom_queue.gate("list_commands"):
        if err := _pre_call("list_commands"):
            return err
        rows = list_catalog(aliases=True)
        return {
            "n": len(rows),
            "commands": rows,
            "read": _subs_listing("read"),
            "do": _subs_listing("do"),
            "aliases": alias_map(),
            "dispatcher": "run_command",
            "hint": (
                "Full phi SPECS catalog. Legacy /slash still parses. "
                "/read <sub> inspects; /do <sub> mutates. "
                "/read help and /do help list umbrella subcommands."
            ),
        }


@mcp.tool()
def run_command(command: str) -> dict[str, Any]:
    """
    Parse a slash command and dispatch it to the matching MCP tool.

    Init-free at this layer — the target tool still runs the session gate
    and the full pre-hook chain. Workflow modes (/talk, /dev, …) return the
    agent-context path instead of calling a tool.

    Parameters
    ----------
    command : raw slash string, e.g. "/read index", "/do sim 1.5",
              "/do commit prompt | thinking | outcome"
    """
    with _dom_queue.gate("run_command"):
        if err := _pre_call("run_command", command=command):
            return err
        try:
            parsed = parse_command(command)
        except CommandParseError as exc:
            return {
                "error": "unknown_command",
                "message": str(exc),
                "command": command,
                "hint": "Call list_commands() for the full catalog.",
            }
        return _invoke(parsed)
