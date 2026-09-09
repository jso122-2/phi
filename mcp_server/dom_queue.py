"""
DOM Request Queue — 6-house serialising gate for the MCP server.

Architecture
------------
At spawn, six Houses are opened — one per workflow mode.  Every tool call
races from spawn to its declared house.  The queue verifies the BMAD trust
token, admits the call through the correct door, and serialises execution
within that lane.

Once inside a house, the call proceeds through and purposeful — no ambiguity
in ordering, no silent state contention.  Calls to *different* houses are
fully parallel; calls to the *same* house are queued.

BMAD Trust
----------
Each house holds a trust token minted at spawn from a deterministic hash of
the house name.  The mapping of tool → house is declared at spawn and is
immutable for the process lifetime.  Tools cannot self-select a different
house; the queue enforces structural trust, not credential-based trust.

    Build   — declare the house mapping at spawn
    Map     — route every tool to exactly one house
    Admit   — verify membership before acquiring the lane lock
    Do      — execute within the serialised lane, then release

Race / Concurrency
------------------
The solved race-condition system already used in HarmonicIndex (threading.RLock)
is promoted here to the queue layer — one RLock per house.  The queue-level
RLock (_queue_lock) protects the house registry during spawn registration only.
After open() is called, the registry is frozen and each house lock operates
independently.

This is slower for the CPU by one lock acquire/release per call (≈ 50–200 ns
per gate crossing), which is completely imperceptible at human interaction
timescales (> 100 ms).

Race Condition Watchdog
-----------------------
RaceWatchdog runs as a daemon thread and polls all houses on a configurable
interval.  It detects two failure modes:

  Stall        — a house has held its lock for longer than stall_threshold_ms.
                 This indicates a hung tool call.
  Contention   — a caller had to block on a house lock (recorded at the gate).
                 The watchdog observes the house contention counter; it never
                 acquires a house lock itself.

Events are recorded in bounded ring-buffers (last 50 of each type).
Call RaceWatchdog.state() to inspect.  The watchdog is started automatically
by spawn_houses() and dies with the process (daemon=True).
"""

from __future__ import annotations

import hashlib
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from mcp_server._guard import MCPToolError


# ---------------------------------------------------------------------------
# House
# ---------------------------------------------------------------------------

_LOCK_TIMEOUT_S = 30.0
"""How long a caller waits for a busy house before the call is rejected."""


class HouseTimeoutError(MCPToolError):
    """Raised when a house lock is not acquired within the timeout."""

    error_code = "house_timeout"

    def __init__(self, house: str, tool: str, timeout_s: float) -> None:
        self.house = house
        self.tool = tool
        self.timeout_s = timeout_s
        super().__init__(
            f"house {house!r} held longer than {timeout_s:.1f}s; "
            f"{tool!r} was not admitted"
        )

    def to_dict(self, tool: str) -> dict[str, Any]:
        payload = super().to_dict(tool)
        payload["house"] = self.house
        payload["timeout_s"] = self.timeout_s
        return payload


class HouseAdmissionError(MCPToolError):
    """
    Raised when a house's BMAD admission predicate does not pass within
    ``admission_timeout_s``.

    The predicate is a state check (e.g. adaptive confidence floor, CSS
    stability, consumption cap) registered at spawn and re-evaluated on a
    50 ms poll loop.  If the system cannot reach the required state in time,
    this error surfaces as a structured dict so the caller can inspect which
    house blocked and why.
    """

    error_code = "house_admission_timeout"

    def __init__(self, house: str, tool: str, timeout_s: float) -> None:
        self.house = house
        self.tool = tool
        self.timeout_s = timeout_s
        super().__init__(
            f"house {house!r} admission predicate did not pass within "
            f"{timeout_s:.1f}s; {tool!r} was deferred"
        )

    def to_dict(self, tool: str) -> dict[str, Any]:
        payload = super().to_dict(tool)
        payload["house"] = self.house
        payload["timeout_s"] = self.timeout_s
        payload["hint"] = (
            "The house admission predicate evaluated False for the full "
            "timeout period.  Check system_status / watchdog_state for the "
            "underlying state (confidence, consumption, coherence, CSS)."
        )
        return payload


@dataclass
class House:
    """
    One of the six entry points — a named, trust-gated, serialised lane.

    Each house owns a fixed set of tool names and a BMAD trust token minted
    at spawn.  The RLock is the same mechanism used by HarmonicIndex, promoted
    to the queue layer.

    Extra fields support the RaceWatchdog:
      _active_since  — monotonic timestamp when the current call entered
      _active_tool   — name of the tool currently executing (empty when idle)
      _contention_count — how many times a caller had to block (cross-thread race)
    """

    name: str
    trust_token: str
    tools: frozenset[str]
    purpose: str

    # Per-house concurrency: one RLock, reentrant so tools can call each other
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)
    _call_count: int = field(default=0, repr=False, compare=False)
    _active: bool = field(default=False, repr=False, compare=False)

    # Watchdog-visible fields (written inside the lock; read by the watchdog thread)
    _active_since: float = field(default=0.0, repr=False, compare=False)
    _active_tool: str = field(default="", repr=False, compare=False)
    _contention_count: int = field(default=0, repr=False, compare=False)

    # BMAD soft-defer admission predicate (optional).
    # Set at spawn via  house._admission_check = lambda: <bool expression>.
    # The gate polls this at _admission_poll_s intervals for up to
    # _admission_timeout_s before raising HouseAdmissionError.
    _admission_check: "Any" = field(default=None, repr=False, compare=False)
    _admission_poll_s: float = field(default=0.05, repr=False, compare=False)
    _admission_timeout_s: float = field(default=10.0, repr=False, compare=False)

    def __post_init__(self) -> None:
        # dataclass default_factory on a mutable field; re-init to be safe
        object.__setattr__(self, "_lock", threading.RLock())

    def admits(self, tool_name: str) -> bool:
        """Return True if this house owns the given tool."""
        return tool_name in self.tools

    def enter(self, tool_name: str, timeout_s: float = _LOCK_TIMEOUT_S) -> "_HouseGate":
        """
        Return a context manager that acquires this house's lock.

        The gate records entry/exit metadata so system_status and the
        RaceWatchdog can report live queue state.  ``timeout_s`` bounds
        how long a caller will block on a busy house.
        """
        return _HouseGate(self, tool_name, timeout_s=timeout_s)

    def status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "tools": sorted(self.tools),
            "call_count": self._call_count,
            "active": self._active,
            "active_tool": self._active_tool,
            "contention_count": self._contention_count,
            "admission_gated": self._admission_check is not None,
            "admission_timeout_s": self._admission_timeout_s,
        }


class _HouseGate:
    """
    Context manager for one tool call's passage through a house.

    Acquire → mark active → execute → mark idle → release.

    Contention detection: a non-blocking acquire attempt is made first.
    If it fails the house lock is already held by another thread — that is
    a real cross-thread race.  The contention counter on the house is
    incremented before the blocking acquire completes.
    """

    __slots__ = ("_house", "_tool_name", "_entered_at", "_timeout_s", "_acquired")

    def __init__(
        self,
        house: House,
        tool_name: str,
        timeout_s: float = _LOCK_TIMEOUT_S,
    ) -> None:
        self._house = house
        self._tool_name = tool_name
        self._entered_at: float = 0.0
        self._timeout_s = timeout_s
        self._acquired = False

    @property
    def house(self) -> House:
        return self._house

    @property
    def tool_name(self) -> str:
        return self._tool_name

    @property
    def elapsed_ms(self) -> float:
        return (time.monotonic() - self._entered_at) * 1000.0

    def __enter__(self) -> "_HouseGate":
        # Phase 1 — BMAD admission predicate (before acquiring the house lock).
        # The lane stays free during this wait so other tools are unaffected.
        # A predicate of None means the house always admits immediately.
        _check = self._house._admission_check
        if _check is not None:
            _deadline = time.monotonic() + self._house._admission_timeout_s
            _poll = self._house._admission_poll_s
            while not _check():
                if time.monotonic() >= _deadline:
                    raise HouseAdmissionError(
                        self._house.name,
                        self._tool_name,
                        self._house._admission_timeout_s,
                    )
                time.sleep(_poll)

        # Phase 2 — acquire the house serialisation lock.
        # Try non-blocking first to detect cross-thread contention.
        # RLock.acquire(blocking=False) returns False only if another
        # thread holds the lock (reentrant same-thread acquire succeeds).
        if not self._house._lock.acquire(blocking=False):
            self._house._contention_count += 1
            if not self._house._lock.acquire(blocking=True, timeout=self._timeout_s):
                raise HouseTimeoutError(
                    self._house.name, self._tool_name, self._timeout_s
                )
        self._acquired = True
        try:
            self._house._active = True
            self._house._active_since = time.monotonic()
            self._house._active_tool = self._tool_name
            self._house._call_count += 1
            self._entered_at = self._house._active_since
            return self
        except Exception:
            self._house._lock.release()
            self._acquired = False
            raise

    def __exit__(self, *_: object) -> None:
        try:
            self._house._active = False
            self._house._active_tool = ""
        finally:
            if self._acquired:
                self._acquired = False
                self._house._lock.release()


# ---------------------------------------------------------------------------
# Race Condition Watchdog
# ---------------------------------------------------------------------------


class RaceWatchdog:
    """
    Daemon thread that monitors the DOM Request Queue for stalled or
    racing tool calls.

    Stall detection
    ---------------
    A house that has been _active for longer than stall_threshold_ms is
    considered stalled — the tool call has likely hung or is unusually slow.
    A stall event is recorded with the house name, tool name, and elapsed ms.

    Contention detection
    --------------------
    When the watchdog finds a house _active it attempts a non-blocking lock
    acquire on the house's RLock.  If the acquire fails, the lock is held by
    the executing tool and the watchdog's contention probe is blocked — this
    confirms live cross-thread contention and is recorded as a contention event.
    The watchdog immediately releases the lock if it did acquire it.

    Both event lists are capped at 50 entries (ring-buffer behaviour).

    Usage
    -----
    Constructed and started automatically by spawn_houses().
    Query via .state() or the `watchdog_state` MCP tool.
    """

    _MAX_EVENTS = 50

    def __init__(
        self,
        queue: "DOMRequestQueue",
        *,
        stall_threshold_ms: float = 5_000.0,
        poll_interval_ms: float = 500.0,
    ) -> None:
        self._queue = queue
        self._stall_threshold = stall_threshold_ms / 1000.0
        self._poll_interval = poll_interval_ms / 1000.0
        self._stall_events: list[dict[str, Any]] = []
        self._contention_events: list[dict[str, Any]] = []
        self._event_lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._stall_keys: set[tuple[str, float]] = set()
        self._contention_seen: dict[str, int] = {}

    def start(self) -> None:
        """Start the watchdog daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._watch_loop,
            daemon=True,
            name="race-watchdog",
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the watchdog to stop (takes effect after the next poll)."""
        self._running = False

    def state(self) -> dict[str, Any]:
        """Serialisable snapshot — safe to call from any thread."""
        with self._event_lock:
            return {
                "running": self._running,
                "stall_threshold_ms": round(self._stall_threshold * 1000.0, 1),
                "poll_interval_ms": round(self._poll_interval * 1000.0, 1),
                "total_stalls": len(self._stall_events),
                "total_contentions": len(self._contention_events),
                "recent_stalls": list(self._stall_events[-10:]),
                "recent_contentions": list(self._contention_events[-10:]),
            }

    # ------------------------------------------------------------------

    def _watch_loop(self) -> None:
        while self._running:
            try:
                self._poll()
            except Exception as exc:
                print(
                    f"[race-watchdog] poll failed: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
            time.sleep(self._poll_interval)

    def _poll(self) -> None:
        now = time.monotonic()
        for house in self._queue._iter_houses():
            if not house._active:
                continue

            elapsed = now - house._active_since

            # Stall check — observe only.  Never acquire the house lock:
            # a watchdog acquire can steal the lane from a waiting caller.
            if elapsed > self._stall_threshold:
                key = (house.name, house._active_since)
                if key not in self._stall_keys:
                    self._stall_keys.add(key)
                    if len(self._stall_keys) > self._MAX_EVENTS * 2:
                        self._stall_keys.clear()
                    self._record_stall(house, elapsed)

            seen = self._contention_seen.get(house.name, 0)
            count = house._contention_count
            if count > seen:
                self._contention_seen[house.name] = count
                self._record_contention(house, elapsed)

    def _record_stall(self, house: "House", elapsed_s: float) -> None:
        event = {
            "ts": round(time.time(), 3),
            "house": house.name,
            "tool": house._active_tool,
            "elapsed_ms": round(elapsed_s * 1000.0, 1),
        }
        with self._event_lock:
            self._stall_events.append(event)
            if len(self._stall_events) > self._MAX_EVENTS:
                self._stall_events.pop(0)
        on_stall = getattr(self._queue, "_on_stall", None)
        if callable(on_stall):
            try:
                on_stall(event)
            except Exception as exc:
                print(
                    f"[race-watchdog] on_stall failed: {exc}",
                    file=sys.stderr,
                    flush=True,
                )

    def _record_contention(self, house: "House", elapsed_s: float) -> None:
        event = {
            "ts": round(time.time(), 3),
            "house": house.name,
            "tool": house._active_tool,
            "elapsed_ms": round(elapsed_s * 1000.0, 1),
        }
        with self._event_lock:
            self._contention_events.append(event)
            if len(self._contention_events) > self._MAX_EVENTS:
                self._contention_events.pop(0)


# ---------------------------------------------------------------------------
# DOM Request Queue
# ---------------------------------------------------------------------------


class DOMRequestQueue:
    """
    The central gate.  Six houses registered at spawn; every tool call races
    to the correct door.

    State machine:
      CLOSED  →  register_house() calls add houses
      OPEN    →  open() freezes the registry; gate() becomes callable
    """

    def __init__(self, lock_timeout_s: float = _LOCK_TIMEOUT_S) -> None:
        self._houses: dict[str, House] = {}
        self._tool_map: dict[str, str] = {}   # tool_name → house_name
        self._queue_lock = threading.RLock()   # guards registry writes during spawn
        self._initialized = False
        self._lock_timeout_s = lock_timeout_s
        self._overflow = House(
            name="overflow",
            trust_token="bmad-overflow-unmapped",
            tools=frozenset(),
            purpose="Unmapped tools — admit, never drop",
        )

    def register_house(self, house: House) -> None:
        """Register a house. Must be called before open()."""
        with self._queue_lock:
            if self._initialized:
                raise RuntimeError("Cannot register a house after the queue is open")
            self._houses[house.name] = house
            for tool in house.tools:
                if tool in self._tool_map:
                    raise ValueError(
                        f"Tool {tool!r} is already registered to house "
                        f"{self._tool_map[tool]!r}; each tool belongs to exactly one house"
                    )
                self._tool_map[tool] = house.name

    def open(self) -> None:
        """Freeze the registry and open the queue for incoming calls."""
        with self._queue_lock:
            if len(self._houses) < 1:
                raise RuntimeError("Cannot open an empty queue — register at least one house first")
            self._initialized = True

    def gate(self, tool_name: str) -> _HouseGate:
        """
        Race entry point — classify the tool, verify membership, return the
        house gate context manager.

        Unknown tools are admitted through the overflow house so a missing
        mapping cannot abort the call.  An unopened queue still raises —
        that is a spawn bug, not a tool bug.
        """
        if not self._initialized:
            raise RuntimeError("DOMRequestQueue has not been opened — call open() at spawn")

        house_name = self._tool_map.get(tool_name)
        if house_name is None:
            house = self._overflow
        else:
            house = self._houses[house_name]
        return house.enter(tool_name, timeout_s=self._lock_timeout_s)

    def _iter_houses(self) -> Any:
        yield from self._houses.values()
        yield self._overflow

    def state(self) -> dict[str, Any]:
        """Serialisable snapshot of all houses — safe to call at any time."""
        with self._queue_lock:
            houses = [h.status() for h in self._houses.values()]
            if self._overflow._call_count:
                houses.append(self._overflow.status())
            return {
                "open": self._initialized,
                "n_houses": len(self._houses),
                "houses": houses,
                "total_calls": sum(h._call_count for h in self._iter_houses()),
            }

    def house_for(self, tool_name: str) -> str | None:
        """Return the house name for a tool (None if unregistered)."""
        return self._tool_map.get(tool_name)


# ---------------------------------------------------------------------------
# BMAD trust tokens
# ---------------------------------------------------------------------------


def _bmad_token(house_name: str) -> str:
    """
    Mint a deterministic BMAD trust token for a house.

    Tokens are stable across restarts — they are structural, not ephemeral.
    The payload encodes project identity + house name + schema version so
    tokens from different projects or queue layouts cannot be cross-applied.

        Build   at spawn, mint one token per house
        Map     bind the token to the house's tool set
        Admit   the gate checks tool membership (token is proof of house identity)
        Do      execute inside the serialised lane
    """
    payload = f"bmad:spotify-rip:{house_name}:dom-queue-v1"
    digest = hashlib.sha256(payload.encode()).hexdigest()[:24]
    return f"bmad-{house_name}-{digest}"


# ---------------------------------------------------------------------------
# spawn_houses — called once at server boot
# ---------------------------------------------------------------------------


def spawn_houses() -> DOMRequestQueue:
    """
    Open the seven doors (six workflow houses + graph).

    Maps every MCP tool to exactly one house, mints BMAD trust tokens, and
    returns an open DOMRequestQueue ready to gate all tool calls.

    House → tool assignments follow the workflow mode semantics from
    .agent-context/:

        talk      simulate and explore the attractor landscape
        dev       build and validate via tests
        modular   propagate and read harmonic structure
        wire      connect knowledge through the harmonic lens (PSSPPS)
        edit      surgical direct injection into a specific shard
        clean     reset, verify, and restore system invariants
        graph     Obsidian vault I/O — the only agent write path into the vault

    The race from spawn: all seven doors open simultaneously.  The first call to
    arrive at any door acquires that house's lock.  Concurrent calls to the
    same house queue behind it.  Calls to different houses proceed in parallel.
    """
    queue = DOMRequestQueue()

    _HOUSES: list[tuple[str, frozenset[str], str]] = [
        (
            "talk",
            frozenset({
                "double_well_sim",
                "neg_exp_sim",
                "sweep_attractors",
                "ana_chi_sim",
                "ana_chi_state",
                "langevin_sim",
                "mfpt_estimate",
            }),
            "Run attractor simulations — explore the dynamical landscape including Ana-Chi",
        ),
        (
            "dev",
            frozenset({"run_tests"}),
            "Build and validate — iterate with tests as the ground-truth signal",
        ),
        (
            "inspect",
            frozenset({
                # Pure-read diagnostic tools — never gated on write pressure.
                # These must always be callable so the system can self-diagnose
                # even when the modular write house is admission-blocked.
                "harmonic_index_state",
                "hub_state",
                "temporal_state",
                "temporal_vector",
                "temporal_coherence",
                "cairrn_hub_state",
                "cairrn_css_state",
                "cairrn_m3_gate",
                "cairrn_neuro_k",
                "code_audit",
                "forecast_state",
                "shuffle_state",
            }),
            "Read-only diagnostics — inspect harmonic, temporal, CAIRRN, and code state",
        ),
        (
            "modular",
            frozenset({
                # Write / propagation tools — admission-gated on CODE pressure.
                "harmonic_propagate",
                "cairrn_hub_run",
                "cairrn_batch_run",
                "rate_ten",
                "shuffle_step",
                "phi_step",
            }),
            "Propagate and shape harmonic/temporal structure — write path only",
        ),
        (
            "wire",
            frozenset({"psspps_query", "find_query", "gemini_clip"}),
            "Connect knowledge — query the Obsidian vault through the harmonic lens",
        ),
        (
            "edit",
            frozenset({
                "harmonic_inject", "hub_inject", "harmonic_set_goal", "harmonic_clear_goal",
                "temporal_record", "temporal_advance", "temporal_reset",
                "shuffle_seed", "shuffle_next",
                "phi_enqueue", "phi_flush",
            }),
            "Surgical injection — directly write activation into a shard, hub, or temporal trace",
        ),
        (
            "clean",
            frozenset({
                "harmonic_reset",
                "init_check",
                "system_status",
                "dom_queue_state",
                "list_hooks",
                "register_hook",
                "vault_hub_state",
                "watchdog_state",
                "phi_queue",
                "bus_poll",
                "bus_status",
                "bus_submit",
                "bus_wait",
                "bus_restart",
                "run_command",
                "list_commands",
            }),
            "Reset and verify — clean state, check health, restore system invariants",
        ),
        (
            "graph",
            frozenset({
                "graph_commit",
                "graph_clean",
                "graph_link",
                "graph_status",
                "graph_nest",
                "graph_ingest",
                "graph_sync_manifest",
                "graph_traverse",
                "graph_topo_hubs",
                "graph_ingest_source",
                "graph_track_state",
                "graph_track_sync",
                "graph_annotate",
            }),
            "Graph worker — commit, clean, link, nest, ingest, traverse, topo hubs, status, usage-track",
        ),
    ]

    for name, tools, purpose in _HOUSES:
        queue.register_house(
            House(
                name=name,
                trust_token=_bmad_token(name),
                tools=tools,
                purpose=purpose,
            )
        )

    queue.open()

    # Start the race condition watchdog — daemon thread, dies with the process
    watchdog = RaceWatchdog(queue, stall_threshold_ms=5_000.0, poll_interval_ms=500.0)
    watchdog.start()
    queue._watchdog: RaceWatchdog = watchdog  # type: ignore[attr-defined, misc]

    return queue
