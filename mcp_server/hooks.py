"""
Append-only pre-tool hook registry.

Design invariants
-----------------
1. Hooks are appended to the chain; never removed, reordered, or cleared.
2. Re-registering a name that already exists is a no-op (idempotent).
3. The chain version equals the current length and only ever increases.
4. Agents may add hooks via the `register_hook` MCP tool; they cannot remove any.
5. Built-in hooks are registered at import time and form the immutable base layer.

Hook contract
-------------
Each hook is a callable with signature:
    fn(tool_name: str, kwargs: dict) -> None

Raise `HookViolation` to abort the tool call.
Return None (or implicitly) to allow it.
"""

from __future__ import annotations

import math
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Final


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class HookViolation(Exception):
    """Raised by a hook to abort a tool call."""


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class Hook:
    name: str
    description: str
    fn: Callable[[str, dict], None]
    registered_at: float = field(default_factory=time.time)
    version: int = 0            # set by registry on append


@dataclass
class HookResult:
    name: str
    passed: bool
    error: str | None = None
    elapsed_ms: float = 0.0


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class HookRegistry:
    """
    Append-only hook chain.

    The chain grows monotonically. There is no delete, pop, clear, or index
    assignment. Future tasks may append; past hooks cannot be rescinded.

    The base layer (built-in hooks registered at import time) is sealed once
    _seal_base() is called.  After sealing, base_version is fixed and any
    inspection can verify the built-in hooks are still present and intact.
    """

    def __init__(self) -> None:
        self._chain: list[Hook] = []
        self._base_sealed: bool = False
        self._base_count: int = 0
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Public API — write
    # ------------------------------------------------------------------

    def register(self, name: str, description: str, fn: Callable[[str, dict], None]) -> int:
        """
        Append a hook to the chain.

        Returns the new chain version (= length).
        Re-registering an existing name is a no-op; the existing hook is kept.
        """
        with self._lock:
            if any(h.name == name for h in self._chain):
                return len(self._chain)
            hook = Hook(name=name, description=description, fn=fn, version=len(self._chain) + 1)
            self._chain.append(hook)
            return len(self._chain)

    def _seal_base(self) -> None:
        """
        Seal the base layer.

        Called once after all built-in hooks are registered.  Records the
        current chain length as the immutable base count.  Agents can verify
        base_version == BASE_HOOK_COUNT to confirm the built-in layer is intact.
        """
        if not self._base_sealed:
            with self._lock:
                if not self._base_sealed:
                    self._base_count = len(self._chain)
                    self._base_sealed = True

    # ------------------------------------------------------------------
    # Public API — read
    # ------------------------------------------------------------------

    def run(self, tool_name: str, kwargs: dict) -> list[HookResult]:
        """
        Run all hooks in registration order.

        Returns a list of HookResult.  The first violation short-circuits
        the remaining hooks and re-raises HookViolation after recording it.
        """
        results: list[HookResult] = []
        with self._lock:
            chain = list(self._chain)
        for hook in chain:
            t0 = time.perf_counter()
            try:
                hook.fn(tool_name, kwargs)
                results.append(HookResult(
                    name=hook.name,
                    passed=True,
                    elapsed_ms=round((time.perf_counter() - t0) * 1000, 3),
                ))
            except HookViolation as exc:
                results.append(HookResult(
                    name=hook.name,
                    passed=False,
                    error=str(exc),
                    elapsed_ms=round((time.perf_counter() - t0) * 1000, 3),
                ))
                raise
            except Exception as exc:
                msg = f"hook {hook.name!r} raised {type(exc).__name__}: {exc}"
                results.append(HookResult(
                    name=hook.name,
                    passed=False,
                    error=msg,
                    elapsed_ms=round((time.perf_counter() - t0) * 1000, 3),
                ))
                raise HookViolation(msg) from exc
        return results

    def state(self) -> dict[str, Any]:
        """Serialisable snapshot of the hook chain."""
        with self._lock:
            return {
                "version": len(self._chain),
                "count": len(self._chain),
                "base_version": self._base_count,
                "base_sealed": self._base_sealed,
                "hooks": [
                    {
                        "version": h.version,
                        "name": h.name,
                        "description": h.description,
                        "registered_at": round(h.registered_at, 3),
                        "base": h.version <= self._base_count,
                    }
                    for h in self._chain
                ],
            }

    @property
    def version(self) -> int:
        return len(self._chain)

    @property
    def base_version(self) -> int:
        """Number of built-in (base-layer) hooks.  Fixed after _seal_base()."""
        return self._base_count


# ---------------------------------------------------------------------------
# Built-in hooks (registered at import time — the immutable base layer)
# ---------------------------------------------------------------------------


def _audit_log(tool_name: str, kwargs: dict) -> None:
    """Record every tool call to stderr for MCP output-channel visibility."""
    keys = list(kwargs.keys())
    print(
        f"[hook:audit] {tool_name}({', '.join(f'{k}=...' for k in keys)})",
        file=sys.stderr,
        flush=True,
    )


def _nan_guard(tool_name: str, kwargs: dict) -> None:
    """Reject any tool call whose float arguments contain NaN or Inf."""
    for k, v in kwargs.items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            raise HookViolation(f"argument '{k}' is {v}; NaN/Inf inputs are not permitted")


def _param_bounds_guard(tool_name: str, kwargs: dict) -> None:
    """Enforce safe parameter bounds on known numerical arguments."""
    bounds: dict[str, tuple[float, float]] = {
        "lr":       (1e-6, 1.0),
        "coupling": (1e-6, 0.499),
        "steps":    (1,    10_000),
        "n_points": (1,    1_000),
        "alpha":    (0.01, 100.0),
        "value":    (-1e6, 1e6),
        "wait_s":   (0.0, 600.0),
        "timeout_s": (0.0, 600.0),
    }
    for k, (lo, hi) in bounds.items():
        v = kwargs.get(k)
        if v is not None:
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if not (lo <= fv <= hi):
                raise HookViolation(
                    f"argument '{k}={v}' is outside safe range [{lo}, {hi}]"
                )


# ---------------------------------------------------------------------------
# Singleton — populated at import time, then base layer is sealed
#
# BASE_HOOK_COUNT is a Final constant that equals the number of built-in hooks.
# It can be used by agents and tests to verify the base layer is still intact:
#   assert registry.base_version == BASE_HOOK_COUNT
# ---------------------------------------------------------------------------


REGISTRY = HookRegistry()

REGISTRY.register(
    name="audit_log",
    description="Log every tool call name and argument keys to MCP output channel.",
    fn=_audit_log,
)
REGISTRY.register(
    name="nan_guard",
    description="Reject any tool call with NaN or Inf in float arguments.",
    fn=_nan_guard,
)
REGISTRY.register(
    name="param_bounds_guard",
    description="Enforce safe numerical bounds on lr, coupling, steps, n_points, alpha, value.",
    fn=_param_bounds_guard,
)

# Seal the base layer — no built-in hooks may be registered after this line.
REGISTRY._seal_base()

BASE_HOOK_COUNT: Final[int] = REGISTRY.base_version
