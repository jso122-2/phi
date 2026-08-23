"""
mcp_server._session_ledger — harmonic trajectory recorder.

Records the initial shard snapshot at gate-open, then appends one entry per
mutation so any tool can compute the delta between *now* and *session start*.

Design notes
------------
- Thread-safe: all writes go through ``_lock`` (reentrant so callers can nest).
- Hub aggregation uses ``HUB_SHARD_MAP`` from ``sims.harmonic`` (lazy import to
  avoid circular deps at module load).
- This module has **no MCP imports** and does not call ``_state`` at load time;
  both sides import it safely.
- BMAD reads ``_total_delta()`` and per-hub deltas so predicates can reflect
  session pressure.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LedgerEntry:
    """One mutation event in the harmonic trajectory."""

    ts: float
    """Unix timestamp (seconds)."""

    tool: str
    """Name of the tool that caused the mutation."""

    snapshot: list[float]
    """Full 8-shard activation vector *after* the mutation."""

    delta: list[float]
    """Per-shard delta vs the *previous* snapshot (or initial if first entry)."""

    step_count: int
    """Value of ``HarmonicIndex.step_count`` after the mutation."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts":         round(self.ts, 3),
            "tool":       self.tool,
            "snapshot":   [round(v, 6) for v in self.snapshot],
            "delta":      [round(v, 6) for v in self.delta],
            "step_count": self.step_count,
        }


class SessionLedger:
    """
    Immutable initial snapshot + append-only mutation log.

    Opened by ``_startup_init`` once the gate flips.  Shared with BMAD via
    ``_total_delta()`` and ``hub_delta(hub_name)``.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._initial: list[float] = []
        self._entries: list[LedgerEntry] = []
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self, snapshot: list[float]) -> None:
        """Record the initial shard state (called once at gate-open)."""
        with self._lock:
            if self._initialized:
                return
            self._initial = list(snapshot)
            self._initialized = True

    def is_open(self) -> bool:
        with self._lock:
            return self._initialized

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, tool: str, snapshot: list[float], step_count: int = 0) -> None:
        """Append a mutation entry; silently no-ops if ledger not yet opened."""
        with self._lock:
            if not self._initialized:
                return
            prev = self._entries[-1].snapshot if self._entries else self._initial
            n = max(len(snapshot), len(prev))
            delta = [
                snapshot[i] - prev[i]
                for i in range(n)
                if i < len(snapshot) and i < len(prev)
            ]
            self._entries.append(LedgerEntry(
                ts=time.time(),
                tool=tool,
                snapshot=list(snapshot),
                delta=delta,
                step_count=step_count,
            ))

    # ------------------------------------------------------------------
    # Query helpers (used by BMAD predicates and coherence_state tool)
    # ------------------------------------------------------------------

    def _total_delta(self) -> list[float]:
        """Per-shard delta from session-start to current snapshot."""
        with self._lock:
            if not self._initialized or not self._entries:
                return [0.0] * len(self._initial)
            current = self._entries[-1].snapshot
            n = max(len(current), len(self._initial))
            return [
                (current[i] if i < len(current) else 0.0)
                - (self._initial[i] if i < len(self._initial) else 0.0)
                for i in range(n)
            ]

    def hub_delta(self, hub_name: str) -> float:
        """Sum of delta activations for all shards belonging to ``hub_name``."""
        try:
            from sims.harmonic import HUB_SHARD_MAP
        except ImportError:
            return 0.0
        indices = HUB_SHARD_MAP.get(hub_name, [])
        total = self._total_delta()
        return sum(total[i] for i in indices if i < len(total))

    def total_pressure(self) -> float:
        """L1 norm of the session-total delta (unsigned accumulated energy)."""
        return sum(abs(d) for d in self._total_delta())

    def code_pressure(self) -> float:
        """Cumulative CODE-hub (shards 3+4) activation change this session."""
        return self.hub_delta("CODE")

    def n_mutations(self) -> int:
        with self._lock:
            return len(self._entries)

    # ------------------------------------------------------------------
    # Serialisation (for coherence_state tool)
    # ------------------------------------------------------------------

    def to_dict(self, tail: int = 10) -> dict[str, Any]:
        """Return a full trajectory summary consumable by MCP tools."""
        with self._lock:
            delta = self._total_delta()
            hub_deltas = {}
            try:
                from sims.harmonic import HUB_NAMES, HUB_SHARD_MAP
                for hub in HUB_NAMES:
                    indices = HUB_SHARD_MAP.get(hub, [])
                    hub_deltas[hub] = round(
                        sum(delta[i] for i in indices if i < len(delta)), 6
                    )
            except ImportError:
                pass

            entries_tail = self._entries[-tail:] if tail > 0 else []
            return {
                "initialized":    self._initialized,
                "n_mutations":    len(self._entries),
                "initial":        [round(v, 6) for v in self._initial],
                "current":        (
                    [round(v, 6) for v in self._entries[-1].snapshot]
                    if self._entries else [round(v, 6) for v in self._initial]
                ),
                "total_delta":    [round(v, 6) for v in delta],
                "hub_delta":      hub_deltas,
                "total_pressure": round(self.total_pressure(), 6),
                "code_pressure":  round(self.code_pressure(), 6),
                "entries":        [e.to_dict() for e in entries_tail],
            }
