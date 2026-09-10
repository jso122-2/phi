#!/usr/bin/env bash
# install_mcp_global.sh — workspaceOpen hook.
#
# Called by Cursor every time this workspace opens on any machine.
# Merges the spotify-rip MCP server entry into ~/.cursor/mcp.json so the
# server is available in ALL repos on this laptop, not just this one.
#
# Input  (stdin): workspaceOpen JSON (ignored)
# Output (stdout): {"pluginPaths": [], "user_message": "..."}
#
# Safe to run repeatedly — idempotent merge, never overwrites other entries.
# Requires Python 3 on PATH (the same interpreter Cursor already needs).

set -euo pipefail

# Read and discard stdin so the hook does not stall.
cat > /dev/null

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PYTHON="${PYTHON_PATH:-python3}"

# Prefer the venv bundled with this repo if available.
VENV_PY="${REPO_ROOT}/.venv/bin/python"
if [[ -x "$VENV_PY" ]]; then
  PYTHON="$VENV_PY"
fi

if ! command -v "$PYTHON" &>/dev/null 2>&1; then
  # Python unavailable — fail open, Cursor continues normally.
  echo '{"pluginPaths":[]}'
  exit 0
fi

"$PYTHON" - "$REPO_ROOT" <<'PYEOF'
import json
import os
import sys
import tempfile
from pathlib import Path

repo_root = Path(sys.argv[1])
project_mcp = repo_root / ".cursor" / "mcp.json"
global_mcp  = Path.home() / ".cursor" / "mcp.json"

# The entry we want present globally — uses ${env:...} so Cursor expands
# the real URL/token from the machine's environment at runtime.
ENTRY = {
    "url": "${env:SPOTIFY_RIP_MCP_URL}",
    "headers": {
        "Authorization": "Bearer ${env:SPOTIFY_RIP_MCP_TOKEN}"
    }
}

def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"mcpServers": {}}

def atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".mcp.", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

existing = load(global_mcp)
servers  = existing.setdefault("mcpServers", {})

already_correct = servers.get("spotify-rip") == ENTRY
if not already_correct:
    servers["spotify-rip"] = ENTRY
    atomic_write(global_mcp, existing)
    msg = "spotify-rip MCP added to ~/.cursor/mcp.json"
else:
    msg = None   # already up to date — silent

payload: dict = {"pluginPaths": []}
if msg:
    payload["user_message"] = msg
print(json.dumps(payload))
PYEOF
