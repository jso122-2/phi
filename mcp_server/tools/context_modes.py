"""
agent_context — callable workflow-mode contracts.

Each slash command (/talk, /dev, /explain, …) dispatches here with a
``mode`` kwarg pre-filled by commands.py.  The tool reads the
corresponding ``.ai_agent_context/<mode>.md`` file and returns its
content as structured JSON so the agent can act on it immediately —
no separate file-read step needed.
"""
from __future__ import annotations

from pathlib import Path

from mcp_server._state import mcp

_CTX_DIR = Path(__file__).resolve().parent.parent.parent / ".ai_agent_context"

MODES: frozenset[str] = frozenset({
    "talk", "explain", "dev", "modular", "wire",
    "edit", "clean", "audit", "read", "find",
})


@mcp.tool()
def agent_context(mode: str) -> dict:
    """
    Return the behaviour contract for a workflow mode.

    Called automatically when the agent dispatches a workflow slash command
    (/talk, /dev, /explain, /modular, /wire, /edit, /clean, /audit, /read,
    /find).  Each invocation reads the matching .ai_agent_context/<mode>.md
    file and returns the full contract text.

    Parameters
    ----------
    mode : one of talk | explain | dev | modular | wire | edit | clean |
           audit | read | find
    """
    if mode not in MODES:
        return {
            "error":       "unknown_mode",
            "mode":        mode,
            "valid_modes": sorted(MODES),
        }

    path = _CTX_DIR / f"{mode}.md"
    if not path.exists():
        return {
            "error":    "missing_contract",
            "mode":     mode,
            "expected": str(path),
        }

    contract = path.read_text(encoding="utf-8")
    return {
        "mode":        mode,
        "contract":    contract,
        "instruction": (
            f"You are now in /{mode} mode. "
            "Read the contract above and follow its behaviour rules "
            "for the remainder of this session."
        ),
    }
