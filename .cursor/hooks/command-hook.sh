#!/usr/bin/env bash
# command-hook.sh — Cursor hook dispatcher for phi slash commands.
# Usage: command-hook.sh <mode>
#   mode: prompt | shell | mcp
#
# Reads JSON from stdin, pipes it to `python -m mcp_server.commands <mode>`,
# writes the JSON response to stdout.
#
# Falls back to "allow / continue" if Python or the module is unavailable.

set -euo pipefail

MODE="${1:-prompt}"
PYTHON="/Users/jack0/mamba/envs/spotify-rip/bin/python"
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

# Read all stdin into a variable so we can feed it to Python.
INPUT="$(cat)"

if [[ ! -x "$PYTHON" ]]; then
  # Env not available — fail open.
  case "$MODE" in
    shell) echo '{"permission":"allow"}' ;;
    *)     echo '{"continue":true}' ;;
  esac
  exit 0
fi

# Pipe the hook payload to the commands module and emit its response.
result=$(
  printf '%s' "$INPUT" \
  | "$PYTHON" -m mcp_server.commands "$MODE" 2>/dev/null
)

if [[ -z "$result" ]]; then
  case "$MODE" in
    shell) echo '{"permission":"allow"}' ;;
    *)     echo '{"continue":true}' ;;
  esac
  exit 0
fi

printf '%s\n' "$result"
