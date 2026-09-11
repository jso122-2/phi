"""Shared MCP config: project mcp.json + Cursor plugin manifests + skill contracts."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_project_mcp_json_has_stdio_entry():
    """Primary entry uses stdio so it works on any local machine with a venv."""
    data = _load(ROOT / ".cursor" / "mcp.json")
    entry = data["mcpServers"]["spotify-rip"]
    assert "command" in entry
    assert entry["args"] == ["-m", "mcp_server.server"]
    assert "cwd" in entry


def test_project_mcp_json_has_local_http_entry():
    """Local HTTP entry connects Cloud Agents to the terminals-started server on localhost:8090."""
    data = _load(ROOT / ".cursor" / "mcp.json")
    entry = data["mcpServers"]["spotify-rip-local-http"]
    assert entry["url"] == "http://localhost:8090/mcp"
    assert "headers" not in entry  # no auth needed — allow-anon on localhost


def test_project_mcp_json_has_cloud_entry():
    """Cloud entry is present as a secondary server for when a hosted server is running."""
    data = _load(ROOT / ".cursor" / "mcp.json")
    entry = data["mcpServers"]["spotify-rip-cloud"]
    assert "command" not in entry
    assert entry["url"] == "${env:SPOTIFY_RIP_MCP_URL}"
    assert "Bearer ${env:SPOTIFY_RIP_MCP_TOKEN}" in entry["headers"]["Authorization"]


def test_environment_json_exists_and_has_mcp_terminal():
    """environment.json must be committed and must start the MCP server as a terminal."""
    env = _load(ROOT / ".cursor" / "environment.json")
    assert "terminals" in env, "No terminals defined"
    commands = [t["command"] for t in env["terminals"]]
    assert any("mcp_server.server" in c and "streamable-http" in c for c in commands), (
        "No terminal starts the MCP HTTP server. Cloud Agents need this to reach the tools."
    )


def test_plugin_mcp_uses_dashboard_variables():
    plugin = _load(ROOT / "cursor-plugin" / ".cursor-plugin" / "plugin.json")
    assert plugin["name"] == "spotify-rip"
    assert set(plugin["variables"]["required"]) == {"MCP_URL", "MCP_TOKEN"}
    mcp = _load(ROOT / "cursor-plugin" / "mcp.json")
    assert mcp["mcpServers"]["spotify-rip"]["url"] == "${MCP_URL}"


def test_marketplace_points_at_plugin_dir():
    market = _load(ROOT / ".cursor-plugin" / "marketplace.json")
    assert market["plugins"][0]["source"] == "cursor-plugin"
    assert market["plugins"][0]["name"] == "spotify-rip"


# ---------------------------------------------------------------------------
# Skill contract path substitution
# ---------------------------------------------------------------------------

def test_skill_contracts_use_repo_root_placeholder():
    """No skill contract should contain a hardcoded user home path."""
    ctx_dir = ROOT / ".ai_agent_context"
    for md in ctx_dir.glob("*.md"):
        text = md.read_text(encoding="utf-8")
        assert "/Users/" not in text, (
            f"{md.name} still contains a hardcoded user path. "
            "Replace with {{REPO_ROOT}}."
        )


def test_context_modes_substitutes_repo_root():
    """_agent_context() must expand {REPO_ROOT} to the actual repo path."""
    from mcp_server.tools.context_modes import _agent_context, _REPO_ROOT
    result = _agent_context("talk")
    assert "{REPO_ROOT}" not in result["contract"], "Placeholder was not expanded"
    assert _REPO_ROOT in result["contract"], "Actual repo path not injected"
