"""
Base worker — unit of computation in the pipeline.

A Worker wraps a callable (sim function, data fetch, transform, etc.)
and runs it with consistent logging, error handling, and result storage.
Subclass and override `_run` to define new worker types.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


class Status(Enum):
    PENDING = auto()
    RUNNING = auto()
    DONE = auto()
    FAILED = auto()


@dataclass
class WorkerResult:
    status: Status
    value: Any = None
    error: str | None = None
    elapsed_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.status == Status.DONE


class Worker:
    """
    Base worker.

    Parameters
    ----------
    name : str
        Human-readable label (used in logs).
    fn   : callable
        The computation to run.  Receives *args and **kwargs passed to
        `run()`.
    """

    def __init__(self, name: str, fn: Callable[..., Any]) -> None:
        self.name = name
        self._fn = fn
        self._history: list[WorkerResult] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, *args: Any, **kwargs: Any) -> WorkerResult:
        """Execute the worker and return a WorkerResult."""
        t0 = time.perf_counter()
        result = self._run(*args, **kwargs)
        result.elapsed_s = round(time.perf_counter() - t0, 6)
        self._history.append(result)
        return result

    @property
    def last(self) -> WorkerResult | None:
        return self._history[-1] if self._history else None

    @property
    def history(self) -> list[WorkerResult]:
        return list(self._history)

    # ------------------------------------------------------------------
    # Override in subclasses
    # ------------------------------------------------------------------

    def _run(self, *args: Any, **kwargs: Any) -> WorkerResult:
        try:
            value = self._fn(*args, **kwargs)
            return WorkerResult(status=Status.DONE, value=value)
        except Exception:
            return WorkerResult(
                status=Status.FAILED,
                error=traceback.format_exc(),
            )

    def __repr__(self) -> str:
        status = self.last.status.name if self.last else "PENDING"
        return f"<Worker name={self.name!r} status={status} runs={len(self._history)}>"


# ---------------------------------------------------------------------------
# Concrete workers
# ---------------------------------------------------------------------------

class SimWorker(Worker):
    """Worker that wraps a sims.* function and stores the trajectory."""

    pass


class BatchWorker:
    """
    Run multiple Workers in sequence and collect results.

    Parameters
    ----------
    workers : list[Worker]
    """

    def __init__(self, workers: list[Worker]) -> None:
        self._workers = workers
        self.results: list[WorkerResult] = []

    def run_all(self, args_list: list[tuple], kwargs_list: list[dict] | None = None) -> list[WorkerResult]:
        """
        Run each worker with corresponding args/kwargs.

        args_list and kwargs_list must have the same length as self._workers.
        """
        if kwargs_list is None:
            kwargs_list = [{} for _ in self._workers]

        self.results = []
        for worker, args, kwargs in zip(self._workers, args_list, kwargs_list):
            result = worker.run(*args, **kwargs)
            self.results.append(result)
        return self.results

    @property
    def all_ok(self) -> bool:
        return all(r.ok for r in self.results)

    def summary(self) -> list[dict]:
        return [
            {
                "worker": w.name,
                "status": r.status.name,
                "elapsed_s": r.elapsed_s,
                "error": r.error,
            }
            for w, r in zip(self._workers, self.results)
        ]
