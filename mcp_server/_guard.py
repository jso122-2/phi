"""
mcp_server._guard — process-lifetime crash envelope for every MCP tool.

Nothing that happens inside a tool body is allowed to:
  - kill the stdio JSON-RPC loop
  - emit a non-JSON-serialisable payload
  - leak a traceback onto stdout (that would corrupt the wire)

install_tool_guard(mcp) wraps FastMCP.tool() *before* any @mcp.tool()
registration, so every subsequently registered tool is guarded.
"""
from __future__ import annotations

import functools
import math
import sys
import traceback
from pathlib import Path
from typing import Any, Callable


class MCPToolError(Exception):
    """
    Expected, structured failure.

    Converted to an error dict without dumping a traceback to stderr.
    Subclass this for gate timeouts and other non-bug failures.
    """

    error_code: str = "tool_error"

    def to_dict(self, tool: str) -> dict[str, Any]:
        return {
            "error": self.error_code,
            "tool": tool,
            "message": str(self),
        }


def json_safe(obj: Any, _depth: int = 0) -> Any:
    """
    Coerce ``obj`` into a JSON-serialisable structure.

    numpy scalars, Path, set, NaN/Inf, and unknown objects are converted.
    Recursion is capped so a cyclic structure cannot hang the server.
    """
    if _depth > 24:
        return "<max_depth>"
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    if isinstance(obj, int) and not isinstance(obj, bool):
        return int(obj)
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {str(k): json_safe(v, _depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v, _depth + 1) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return [json_safe(v, _depth + 1) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    # numpy scalar / 0-d array: .item() → Python native
    item = getattr(obj, "item", None)
    if callable(item) and not isinstance(obj, (bytes, bytearray)):
        try:
            if getattr(obj, "shape", None) == () or getattr(obj, "ndim", 1) == 0:
                return json_safe(item(), _depth + 1)
        except Exception:
            pass
    tolist = getattr(obj, "tolist", None)
    if callable(tolist):
        try:
            return json_safe(tolist(), _depth + 1)
        except Exception:
            pass
    try:
        import json as _json
        _json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return repr(obj)


def tool_error(tool: str, exc: BaseException) -> dict[str, Any]:
    """Structured error payload for an unexpected exception."""
    return {
        "error": "tool_exception",
        "tool": tool,
        "type": type(exc).__name__,
        "message": str(exc) or type(exc).__name__,
    }


def invoke_guarded(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run ``fn`` and always return a JSON-safe value."""
    name = getattr(fn, "__name__", "tool")
    try:
        result = fn(*args, **kwargs)
    except MCPToolError as exc:
        return json_safe(exc.to_dict(name))
    except Exception as exc:
        print(
            f"[mcp_server._guard] {name} raised {type(exc).__name__}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        traceback.print_exc(file=sys.stderr)
        return json_safe(tool_error(name, exc))
    return json_safe(result)


def install_tool_guard(mcp: Any) -> None:
    """
    Wrap ``mcp.tool`` so every subsequently registered tool runs through
    ``invoke_guarded``.  Idempotent — a second call is a no-op.
    """
    if getattr(mcp, "_spotify_rip_guarded", False):
        return
    original = mcp.tool

    def tool(*dargs: Any, **dkwargs: Any) -> Callable[[Callable], Callable]:
        deco = original(*dargs, **dkwargs)

        def register(fn: Callable) -> Callable:
            @functools.wraps(fn)
            def guarded(*args: Any, **kwargs: Any) -> Any:
                return invoke_guarded(fn, *args, **kwargs)

            return deco(guarded)

        return register

    mcp.tool = tool  # type: ignore[method-assign]
    mcp._spotify_rip_guarded = True
