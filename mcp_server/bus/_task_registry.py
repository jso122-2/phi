"""Task registry: @task decorator, TASKS dict, run_task dispatcher."""
from __future__ import annotations

from typing import Any, Callable

from mcp_server._guard import json_safe

TASKS: dict[str, Callable[..., Any]] = {}


def task(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register a bus task under ``name``. Used as a decorator."""
    def _wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        TASKS[name] = fn
        return fn
    return _wrap


def run_task(name: str, kwargs: dict[str, Any] | None = None) -> Any:
    """Dispatch a registered bus task by name. Raises KeyError for unknown tasks."""
    fn = TASKS.get(name)
    if fn is None:
        raise KeyError(f"unknown bus task: {name}")
    return json_safe(fn(**(kwargs or {})))
