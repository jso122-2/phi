"""Shared MCP config: project mcp.json + Cursor plugin manifests."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_project_mcp_json_is_remote_http():
    data = _load(ROOT / ".cursor" / "mcp.json")
    entry = data["mcpServers"]["spotify-rip"]
    assert "command" not in entry
    assert entry["url"] == "${env:SPOTIFY_RIP_MCP_URL}"
    assert "Bearer ${env:SPOTIFY_RIP_MCP_TOKEN}" in entry["headers"]["Authorization"]


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
