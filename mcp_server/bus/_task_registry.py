"""Task registry: @task decorator, TASKS dict, run_task dispatcher.

Job-ID injection
----------------
Tasks that need their own job ID (e.g. for in-transit batching) declare a
``_job_id: str = ""`` parameter.  ``run_task`` detects this via signature
inspection and injects the live job ID automatically.  All other tasks are
unaffected — the injection is strictly opt-in.
"""
from __future__ import annotations

import inspect
from typing import Any, Callable

from mcp_server._guard import json_safe

TASKS: dict[str, Callable[..., Any]] = {}

# Cache which tasks accept _job_id so we don't re-inspect on every call.
_TASKS_WANT_JOB_ID: set[str] = set()


def task(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register a bus task under ``name``. Used as a decorator."""
    def _wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        TASKS[name] = fn
        if "_job_id" in inspect.signature(fn).parameters:
            _TASKS_WANT_JOB_ID.add(name)
        return fn
    return _wrap


def run_task(name: str, kwargs: dict[str, Any] | None = None, job_id: str = "") -> Any:
    """
    Dispatch a registered bus task by name.

    Parameters
    ----------
    name   : registered task name (e.g. ``"notion.tick"``)
    kwargs : payload kwargs from the job record
    job_id : the dispatching job's ID; injected as ``_job_id`` for tasks
             that declare that parameter (opt-in, detected at registration time)

    Raises KeyError for unknown tasks.
    """
    fn = TASKS.get(name)
    if fn is None:
        raise KeyError(f"unknown bus task: {name}")
    kw = dict(kwargs or {})
    if name in _TASKS_WANT_JOB_ID:
        kw.setdefault("_job_id", job_id)
    return json_safe(fn(**kw))
