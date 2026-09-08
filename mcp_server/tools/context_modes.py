"""
context_modes — named MCP tools for each workflow mode.

Each function is a direct @mcp.tool() so it appears in Cursor's / dropdown.
Internally they all call _agent_context(mode) which reads the matching
.ai_agent_context/<mode>.md file and returns the contract + instruction.
"""
from __future__ import annotations

from pathlib import Path

from mcp_server._state import mcp

_CTX_DIR = Path(__file__).resolve().parent.parent.parent / ".ai_agent_context"

MODES: frozenset[str] = frozenset({
    "talk", "explain", "dev", "modular", "wire",
    "edit", "clean", "audit", "read", "find",
})


def _agent_context(mode: str) -> dict:
    """Shared implementation — reads .ai_agent_context/<mode>.md."""
    if mode not in MODES:
        return {"error": "unknown_mode", "mode": mode, "valid_modes": sorted(MODES)}
    path = _CTX_DIR / f"{mode}.md"
    if not path.exists():
        return {"error": "missing_contract", "mode": mode, "expected": str(path)}
    return {
        "mode":        mode,
        "contract":    path.read_text(encoding="utf-8"),
        "instruction": (
            f"You are now in /{mode} mode. "
            "Read the contract above and follow its behaviour rules "
            "for the remainder of this session."
        ),
    }


# ---------------------------------------------------------------------------
# One named tool per mode — these appear individually in Cursor's / dropdown
# ---------------------------------------------------------------------------

@mcp.tool()
def talk() -> dict:
    """
    /talk — Strategic discussion mode.
    Spawns a fresh agent to align on direction before building. Read-only.
    """
    return _agent_context("talk")


@mcp.tool()
def explain() -> dict:
    """
    /explain — Plain-language explanation mode.
    Spawns a fresh agent to explain one thing clearly. No code changes.
    """
    return _agent_context("explain")


@mcp.tool()
def dev() -> dict:
    """
    /dev — Build mode.
    Spawns a fresh agent: read → state → act loop with test + commit.
    """
    return _agent_context("dev")


@mcp.tool()
def modular() -> dict:
    """
    /modular — Package raw output.
    Spawns a fresh agent to turn scripts into proper importable Python packages.
    """
    return _agent_context("modular")


@mcp.tool()
def wire() -> dict:
    """
    /wire — Connect imports, interfaces, pipeline.
    Spawns a fresh agent that traces import chains until /do test passes.
    """
    return _agent_context("wire")


@mcp.tool()
def edit() -> dict:
    """
    /edit — Surgical inline fix.
    Spawns a fresh agent: name the bug, minimal diff, verify.
    """
    return _agent_context("edit")


@mcp.tool()
def clean() -> dict:
    """
    /clean — File tree cleanup.
    Spawns a fresh agent: move, delete, normalise, gitignore. No logic changes.
    """
    return _agent_context("clean")


@mcp.tool()
def audit() -> dict:
    """
    /audit — Three-layer health audit.
    Spawns a fresh agent: env → vault graph → codebase. Returns action list.
    """
    return _agent_context("audit")


@mcp.tool()
def read_mode() -> dict:
    """
    /read — Inspect umbrella.
    Returns the full dispatch table for all /read <sub> commands.
    """
    return _agent_context("read")


@mcp.tool()
def find_mode(query: str = "") -> dict:
    """
    /find — Hybrid search.
    Searches Notion (user-Notion MCP) first, then vault find_query fallback.
    Pass query as the search string.
    """
    result = _agent_context("find")
    if query:
        result["query"] = query
    return result
