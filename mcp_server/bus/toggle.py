"""Cursor MCP enable switch — flip `disabled` off then on to force a respawn."""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

from graph.node import VAULT_ROOT
from mcp_server.bus.runtime import ensure_runtime, last_toggle_path, toggle_lock_path

SERVER_KEY = "spotify-rip"
OFF_HOLD_S = 0.45
MIN_GAP_S = 12.0


def mcp_config_paths() -> list[Path]:
    """User + project copies Cursor actually reads for this workspace."""
    return [
        Path.home() / ".cursor" / "mcp.json",
        VAULT_ROOT.parent / ".cursor" / "mcp.json",
        VAULT_ROOT / ".cursor" / "mcp.json",
    ]


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".mcp.", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def set_disabled(
    flag: bool,
    *,
    paths: Sequence[Path] | None = None,
) -> list[str]:
    """Set or clear `disabled` on the spotify-rip server entry. Returns touched paths."""
    touched: list[str] = []
    for path in paths if paths is not None else mcp_config_paths():
        path = Path(path)
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        servers = data.get("mcpServers")
        if not isinstance(servers, dict) or SERVER_KEY not in servers:
            continue
        entry = servers[SERVER_KEY]
        if not isinstance(entry, dict):
            continue
        if flag:
            entry["disabled"] = True
        else:
            entry["disabled"] = False
        servers[SERVER_KEY] = entry
        data["mcpServers"] = servers
        _atomic_write(path, data)
        touched.append(str(path))
    return touched


def bounce(
    *,
    paths: Sequence[Path] | None = None,
    off_hold_s: float = OFF_HOLD_S,
) -> dict[str, Any]:
    """Toggle the Cursor MCP switch off, wait, then on. That is the respawn."""
    ensure_runtime()
    lock = toggle_lock_path()
    if lock.exists():
        age = time.time() - lock.stat().st_mtime
        if age < MIN_GAP_S:
            return {"skipped": "toggle_lock", "age_s": round(age, 3)}
    lock.write_text(str(time.time()), encoding="utf-8")
    try:
        off = set_disabled(True, paths=paths)
        time.sleep(max(0.05, float(off_hold_s)))
        on = set_disabled(False, paths=paths)
        record = {
            "toggled_at": time.time(),
            "off": off,
            "on": on,
            "off_hold_s": off_hold_s,
        }
        last_toggle_path().write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return record
    finally:
        try:
            lock.unlink(missing_ok=True)
        except OSError:
            pass


def last_toggle() -> dict[str, Any] | None:
    path = last_toggle_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def seconds_since_toggle() -> float | None:
    rec = last_toggle()
    if rec is None:
        return None
    try:
        return max(0.0, time.time() - float(rec["toggled_at"]))
    except (KeyError, TypeError, ValueError):
        return None


def can_bounce(min_gap_s: float = MIN_GAP_S) -> bool:
    gap = seconds_since_toggle()
    return gap is None or gap >= min_gap_s
