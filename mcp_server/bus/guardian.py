"""Sidecar: when the MCP stdio process dies or Cursor marks it failed, bounce the switch.

Cursor treats some disconnects as non-retryable. The recovery is the same
toggle the UI uses: disabled=true, then disabled=false, which respawns stdio.
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys
import time
from pathlib import Path

from mcp_server.bus.client import worker_alive
from mcp_server.bus.runtime import (
    ensure_runtime,
    guardian_log_path,
    guardian_pid_path,
    stdio_pid_path,
)
from mcp_server.bus.toggle import bounce, can_bounce

POLL_S = 1.0
ERROR_MARKERS = (
    "transport_error",
    "conn=failed",
    "failed during live tool discovery",
    "non-retryable error server: user-spotify-rip",
    "non-retryable error server: project-0-Spotify-Rip-spotify-rip",
    "Client error: Unexpected token",
    "Client error: Unexpected non-whitespace",
)


def _read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (TypeError, ValueError):
        return None


def _alive(pid: int | None) -> bool:
    if pid is None:
        return False
    return worker_alive(pid)


def _write_pid(path: Path, pid: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid), encoding="utf-8")


def _cursor_log_paths() -> list[Path]:
    root = Path.home() / "Library" / "Application Support" / "Cursor" / "logs"
    if not root.exists():
        return []
    patterns = (
        "**/mcp-server-user-spotify-rip.log",
        "**/mcp-server-project-*-spotify-rip.log",
        "**/mcp-server-project-*-Spotify-Rip-spotify-rip.log",
        "**/mcp-server-project-*-Spotify-rip-spotify-rip.log",
    )
    found: list[Path] = []
    for pattern in patterns:
        found.extend(Path(p) for p in glob.glob(str(root / pattern), recursive=True))
    return found


class _LogTail:
    def __init__(self) -> None:
        self._pos: dict[str, int] = {}

    def new_error(self) -> bool:
        hit = False
        for path in _cursor_log_paths():
            try:
                size = path.stat().st_size
            except OSError:
                continue
            key = str(path)
            pos = self._pos.get(key, max(0, size - 8192))
            if size < pos:
                pos = 0
            try:
                with path.open("rb") as handle:
                    handle.seek(pos)
                    chunk = handle.read().decode("utf-8", errors="replace")
            except OSError:
                continue
            self._pos[key] = size
            if any(marker in chunk for marker in ERROR_MARKERS):
                hit = True
        return hit


def _mcp_stdio_pids() -> list[int]:
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", " -m mcp_server.server"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pid = _read_pid(stdio_pid_path())
        return [pid] if pid is not None else []
    return [int(x) for x in out.split() if x.strip().isdigit()]


def _stdio_down() -> bool:
    live = [pid for pid in _mcp_stdio_pids() if _alive(pid)]
    return not live


def loop(parent_pid: int | None = None) -> None:
    ensure_runtime()
    _write_pid(guardian_pid_path(), os.getpid())
    if parent_pid:
        _write_pid(stdio_pid_path(), parent_pid)
    tail = _LogTail()
    tail.new_error()  # skip historical errors
    while True:
        time.sleep(POLL_S)
        down = _stdio_down()
        errored = tail.new_error()
        if not down and not errored:
            continue
        if not can_bounce():
            continue
        bounce()


def guardian_alive() -> bool:
    return _alive(_read_pid(guardian_pid_path()))


def ensure_guardian(parent_pid: int) -> dict[str, object]:
    """Spawn the sidecar once. No-op during pytest or unless MCP_TOGGLE_GUARDIAN=1."""
    ensure_runtime()
    _write_pid(stdio_pid_path(), parent_pid)
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {"spawned": False, "reason": "pytest"}
    if os.environ.get("MCP_TOGGLE_GUARDIAN", "0") != "1":
        return {"spawned": False, "reason": "toggle_off"}
    if guardian_alive():
        return {
            "spawned": False,
            "reason": "already_running",
            "pid": _read_pid(guardian_pid_path()),
        }

    log_path = guardian_log_path()
    log_f = open(log_path, "ab", buffering=0)
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["MCP_TOGGLE_GUARDIAN"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_server.bus.guardian", str(parent_pid)],
        cwd=str(Path(__file__).resolve().parents[2]),
        stdin=subprocess.DEVNULL,
        stdout=log_f,
        stderr=log_f,
        env=env,
        start_new_session=True,
    )
    _write_pid(guardian_pid_path(), proc.pid)
    return {"spawned": True, "pid": proc.pid}


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    parent: int | None = None
    if args:
        try:
            parent = int(args[0])
        except ValueError:
            parent = None
    try:
        loop(parent)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
