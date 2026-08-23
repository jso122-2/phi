"""
mcp_server.tools — MCP tool registry.

Importing this package triggers all @mcp.tool() registrations.

Cursor catalog cap
------------------
Cursor truncates each MCP server's tool list at 60 names.  Keep the number of
@mcp.tool() registrations at or below CURSOR_MCP_TOOL_CAP so the dispatcher
(run_command / list_commands), graph_annotate, code_audit, and the CAIRRN
extras stay visible.  Functions without @mcp.tool() remain callable through
run_command (slash specs in mcp_server.commands).

Startup resilience
------------------
Each tool module is loaded individually inside try-except so that a single
broken module (bad import, missing dependency, syntax error) cannot prevent
the rest from registering.  Failed modules are recorded in `load_errors` and
surfaced via init_check() / system_status().
"""
from __future__ import annotations

import sys

CURSOR_MCP_TOOL_CAP = 60
"""Cursor's per-server MCP tool catalog limit. Do not exceed this."""

_TOOL_MODULES = [
    "command",
    "bus",
    "cairrn",
    "forecast",
    "graph",
    "harmonic",
    "search",
    "sims",
    "system",
    "temporal",
    "phi_clip",
    "prefeed_shuffle",
    "phi_dispatch",
    "modular",
]

load_errors: dict[str, str] = {}
"""Populated at import time for any tool module that failed to load."""

for _mod in _TOOL_MODULES:
    try:
        __import__(f"mcp_server.tools.{_mod}")
    except Exception as _exc:
        load_errors[_mod] = str(_exc)
        print(
            f"[mcp_server.tools] {_mod} failed to load: {_exc}",
            file=sys.stderr,
        )

if load_errors:
    print(
        f"[mcp_server.tools] {len(load_errors)} module(s) failed: "
        f"{list(load_errors)}",
        file=sys.stderr,
    )
