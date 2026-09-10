"""
Tests for the cross-device MCP sync utilities:
  - scripts/setup_mcp.py  (idempotent global installer)
  - .cursor/hooks/install_mcp_global.sh  (workspaceOpen hook)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SETUP_PY = ROOT / "scripts" / "setup_mcp.py"
HOOK_SH = ROOT / ".cursor" / "hooks" / "install_mcp_global.sh"


# ---------------------------------------------------------------------------
# setup_mcp.py
# ---------------------------------------------------------------------------

def test_install_writes_placeholder_url(tmp_path: Path) -> None:
    """When no URL/token supplied, placeholders are written so Cursor expands them."""
    target = tmp_path / "mcp.json"
    from scripts.setup_mcp import install
    changed = install(target=target)
    assert changed
    data = json.loads(target.read_text())
    entry = data["mcpServers"]["spotify-rip"]
    assert entry["url"] == "${env:SPOTIFY_RIP_MCP_URL}"
    assert "${env:SPOTIFY_RIP_MCP_TOKEN}" in entry["headers"]["Authorization"]


def test_install_writes_concrete_values(tmp_path: Path) -> None:
    target = tmp_path / "mcp.json"
    from scripts.setup_mcp import install
    install(url="https://mcp.example.com/mcp", token="s3cr3t", target=target)
    data = json.loads(target.read_text())
    entry = data["mcpServers"]["spotify-rip"]
    assert entry["url"] == "https://mcp.example.com/mcp"
    assert entry["headers"]["Authorization"] == "Bearer s3cr3t"


def test_install_idempotent(tmp_path: Path) -> None:
    """Second call with same values returns changed=False."""
    target = tmp_path / "mcp.json"
    from scripts.setup_mcp import install
    install(url="https://x/mcp", token="tok", target=target)
    changed = install(url="https://x/mcp", token="tok", target=target)
    assert not changed


def test_install_merges_existing_servers(tmp_path: Path) -> None:
    """Other server entries must survive."""
    target = tmp_path / "mcp.json"
    target.write_text(json.dumps({
        "mcpServers": {
            "other-server": {"url": "https://other.example.com/mcp"}
        }
    }))
    from scripts.setup_mcp import install
    install(target=target)
    data = json.loads(target.read_text())
    assert "other-server" in data["mcpServers"]
    assert "spotify-rip" in data["mcpServers"]


def test_install_creates_cursor_dir_if_missing(tmp_path: Path) -> None:
    target = tmp_path / ".cursor" / "mcp.json"
    assert not target.parent.exists()
    from scripts.setup_mcp import install
    install(target=target)
    assert target.exists()


def test_install_dry_run_does_not_write(tmp_path: Path) -> None:
    target = tmp_path / "mcp.json"
    from scripts.setup_mcp import install
    changed = install(target=target, dry_run=True)
    assert changed
    assert not target.exists()


def test_cli_entrypoint_dry_run(tmp_path: Path) -> None:
    target = tmp_path / "mcp.json"
    result = subprocess.run(
        [sys.executable, str(SETUP_PY), "--dry-run", "--target", str(target)],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    assert result.returncode == 0
    assert "dry-run" in result.stdout
    assert not target.exists()


def test_cli_entrypoint_with_args(tmp_path: Path) -> None:
    target = tmp_path / "mcp.json"
    result = subprocess.run(
        [sys.executable, str(SETUP_PY),
         "--url", "https://mcp.example.com/mcp",
         "--token", "tok",
         "--target", str(target)],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    assert result.returncode == 0
    data = json.loads(target.read_text())
    assert data["mcpServers"]["spotify-rip"]["url"] == "https://mcp.example.com/mcp"


# ---------------------------------------------------------------------------
# .cursor/hooks/install_mcp_global.sh
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HOOK_SH.exists(), reason="hook script not found")
def test_hook_script_is_executable() -> None:
    assert HOOK_SH.stat().st_mode & 0o111


@pytest.mark.skipif(not HOOK_SH.exists(), reason="hook script not found")
def test_hook_script_produces_valid_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pipe a fake workspaceOpen payload through the hook and check output."""
    import os
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    result = subprocess.run(
        ["bash", str(HOOK_SH)],
        input='{"hook_event_name":"workspaceOpen","workspace_roots":["/tmp"],"cursor_version":"1.0"}',
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout.strip())
    assert "pluginPaths" in output


@pytest.mark.skipif(not HOOK_SH.exists(), reason="hook script not found")
def test_hook_script_writes_global_mcp(tmp_path: Path) -> None:
    import os
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    subprocess.run(
        ["bash", str(HOOK_SH)],
        input='{}', capture_output=True, text=True, env=env,
    )
    global_mcp = tmp_path / ".cursor" / "mcp.json"
    assert global_mcp.exists()
    data = json.loads(global_mcp.read_text())
    entry = data["mcpServers"]["spotify-rip"]
    assert "url" in entry
    assert "${env:SPOTIFY_RIP_MCP_URL}" in entry["url"]


@pytest.mark.skipif(not HOOK_SH.exists(), reason="hook script not found")
def test_hook_script_idempotent(tmp_path: Path) -> None:
    """Running the hook twice must not corrupt the file."""
    import os
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    for _ in range(2):
        subprocess.run(
            ["bash", str(HOOK_SH)],
            input='{}', capture_output=True, text=True, env=env,
        )
    global_mcp = tmp_path / ".cursor" / "mcp.json"
    data = json.loads(global_mcp.read_text())
    assert list(data["mcpServers"].keys()) == ["spotify-rip"]


# ---------------------------------------------------------------------------
# hooks.json includes workspaceOpen
# ---------------------------------------------------------------------------

def test_hooks_json_has_workspace_open() -> None:
    hooks_json = ROOT / ".cursor" / "hooks.json"
    data = json.loads(hooks_json.read_text())
    hooks = data.get("hooks", {})
    assert "workspaceOpen" in hooks
    cmds = [h.get("command", "") for h in hooks["workspaceOpen"]]
    assert any("install_mcp_global" in c for c in cmds)
