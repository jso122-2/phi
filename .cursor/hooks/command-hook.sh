#!/usr/bin/env bash
# Cursor pre-hooks → mcp_server.commands.hook_main
# Modes: prompt | shell | mcp   (also hook-prompt, hook-shell, hook-mcp)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MODE="${1:-prompt}"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi
exec "$PY" -m mcp_server.commands "$MODE"
