"""
Allows the engine package to be run as a module from any working directory:

    python -m engine [--once] [--dry-run] [--interval N] ...

Equivalent to running engine.coherence_daemon directly, but with the project
root automatically resolved so `inference`, `models`, and `data` are importable
regardless of cwd.
"""
import sys
from pathlib import Path

# Resolve project root (two levels up from this file: engine/__main__.py → samba-gnn-obsidian/)
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from engine.coherence_daemon import main

main()
