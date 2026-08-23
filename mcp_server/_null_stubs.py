"""
Null stubs for failed singleton inits.

Assigned at startup when the real singleton fails to build, so every tool
body can still execute without crashing on import-time AttributeError.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any


class _NullDOMQueue:
    """
    Drop-in replacement when spawn_houses() fails at startup.

    gate() returns a no-op context manager so every tool body still runs.
    Serialisation and race-watchdog features are absent; all tools execute
    in an unguarded single-threaded context until the server is restarted.
    """

    @contextmanager
    def gate(self, tool_name: str):  # type: ignore[override]
        yield

    def state(self) -> dict[str, Any]:
        return {
            "open": False,
            "error": "startup_failed",
            "hint": "check startup_errors in init_check()",
            "n_houses": 0,
            "houses": [],
            "total_calls": 0,
        }

    def house_for(self, tool_name: str) -> str | None:
        return None


class _NullVaultHub:
    """
    Drop-in replacement when open_vault_hub() fails at startup.

    All push_* methods are silent no-ops so tools never crash on
    backwards-channel writes.
    """

    LIVE_STATE_FILE = "live-state.md"
    _push_count: int = 0
    _harmonic: dict[str, Any] = {}
    _last_sim: dict[str, Any] = {}
    _queue: dict[str, Any] = {}

    def __init__(self) -> None:
        self._vault_dir = Path(".")

    def push_harmonic(self, state: dict[str, Any]) -> None:
        pass

    def push_sim(self, tool_name: str, result: dict[str, Any]) -> None:
        pass

    def push_queue(self, state: dict[str, Any]) -> None:
        pass

    def push_forecast(self, state: dict[str, Any]) -> None:
        pass

    def push_all(self, **kwargs: Any) -> None:
        pass
