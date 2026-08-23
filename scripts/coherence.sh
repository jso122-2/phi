#!/usr/bin/env bash
# Vault Coherence Engine launcher — run from anywhere.
# Usage:  ./coherence [--once] [--dry-run] [--interval 300] [--help]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Resolve Python: honour SAMBA_PYTHON env var, then try the active venv/conda
# env, then fall back to python3 on PATH.
if [[ -n "${SAMBA_PYTHON:-}" ]]; then
    PYTHON="$SAMBA_PYTHON"
elif command -v micromamba &>/dev/null && micromamba run -n spot python --version &>/dev/null 2>&1; then
    PYTHON="micromamba run -n spot python"
elif [[ -n "${CONDA_PREFIX:-}" ]] && [[ -x "$CONDA_PREFIX/bin/python" ]]; then
    PYTHON="$CONDA_PREFIX/bin/python"
elif [[ -n "${VIRTUAL_ENV:-}" ]] && [[ -x "$VIRTUAL_ENV/bin/python" ]]; then
    PYTHON="$VIRTUAL_ENV/bin/python"
else
    PYTHON="$(command -v python3 || command -v python)"
fi

exec $PYTHON - "$@" <<EOF
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from engine.coherence_daemon import main
main()
EOF
