"""
mcp_server._state — process-lifetime singletons.

All stateful objects shared across tool modules live here. Import from this
module; never construct a second instance anywhere.

Startup resilience
------------------
Every singleton init is wrapped in try-except. A failed init is recorded in
`startup_errors` (visible via init_check / system_status) and a null-stub is
assigned so the module always imports cleanly.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

from mcp_server._null_stubs import _NullDOMQueue, _NullVaultHub  # noqa: F401 (re-exported)
from mcp_server._guard import install_tool_guard

from mcp.server.fastmcp import FastMCP

# Runtime snapshot — vault root, survives server restarts (gitignored).
# Override with SPOTIFY_RIP_HARMONIC_SNAPSHOT for tests.
_VAULT_ROOT: Path = Path(__file__).parent.parent
_HARMONIC_SNAPSHOT: Path = Path(
    os.environ.get(
        "SPOTIFY_RIP_HARMONIC_SNAPSHOT",
        str(_VAULT_ROOT / ".harmonic-snapshot.json"),
    )
)
_LEGACY_HARMONIC_SNAPSHOT: Path = _VAULT_ROOT / "Spotify-rip" / ".harmonic-snapshot.json"

# ---------------------------------------------------------------------------
# Startup error registry
# ---------------------------------------------------------------------------

startup_errors: dict[str, str] = {}
"""Populated at import time if any singleton fails to initialise."""

# ---------------------------------------------------------------------------
# FastMCP server singleton (must succeed — no fallback possible)
# ---------------------------------------------------------------------------

mcp = FastMCP(
    os.environ.get("SPOTIFY_RIP_MCP_NAME", "spotify-rip"),
    instructions=(
        "Tooling server for the spotify-rip dynamical-systems project. "
        "Enforces environment initialisation, runs attractor simulations, "
        "and manages the harmonically-sharded propagation index. "
        "Vault search is first-class: call find_query / psspps_query; "
        "do not shell out to psspps Python."
    ),
)
install_tool_guard(mcp)

# ---------------------------------------------------------------------------
# Shared locks
# ---------------------------------------------------------------------------

_lazy_lock = threading.Lock()
"""Guards first-use construction of VPN + forecasting singletons."""

_adaptive_lock = threading.Lock()
"""Guards CAIRRN coherence writes."""

# ---------------------------------------------------------------------------
# Harmonic index + ticket clipper
# ---------------------------------------------------------------------------

_harmonic_index: Any = None
_ticket_clipper: Any = None

try:
    from sims.harmonic import HarmonicIndex, TicketClipper
    _harmonic_index = HarmonicIndex(n_harmonics=8, coupling=0.15)
    _ticket_clipper = TicketClipper(_harmonic_index, threshold=0.01)
except Exception as _exc:
    startup_errors["harmonic"] = str(_exc)
    print(f"[mcp_server._state] harmonic init failed: {_exc}", file=sys.stderr)

# ---------------------------------------------------------------------------
# Session ledger — harmonic trajectory recorder
# ---------------------------------------------------------------------------

from mcp_server._session_ledger import SessionLedger  # noqa: E402

_session_ledger: SessionLedger = SessionLedger()
"""Process-lifetime harmonic trajectory ledger. Opened at gate-open."""

# ---------------------------------------------------------------------------
# Temporal shard index
# ---------------------------------------------------------------------------

_temporal_index: Any = None

try:
    from sims.temporal import TemporalShardIndex
    _temporal_index = TemporalShardIndex(n_windows=8)
except Exception as _exc:
    startup_errors["temporal"] = str(_exc)
    print(f"[mcp_server._state] temporal init failed: {_exc}", file=sys.stderr)

# ---------------------------------------------------------------------------
# DOM request queue
# ---------------------------------------------------------------------------

try:
    from mcp_server.dom_queue import spawn_houses
    _dom_queue = spawn_houses()
except Exception as _exc:
    startup_errors["dom_queue"] = str(_exc)
    print(f"[mcp_server._state] dom_queue init failed: {_exc}", file=sys.stderr)
    _dom_queue: Any = _NullDOMQueue()

# ---------------------------------------------------------------------------
# Vault hub (backwards channel: MCP state → Obsidian vault)
# ---------------------------------------------------------------------------

try:
    from mcp_server.vault_hub import open_vault_hub
    _vault_hub = open_vault_hub(Path(__file__).parent.parent)
except Exception as _exc:
    startup_errors["vault_hub"] = str(_exc)
    print(f"[mcp_server._state] vault_hub init failed: {_exc}", file=sys.stderr)
    _vault_hub: Any = _NullVaultHub()

# ---------------------------------------------------------------------------
# Lazy singletons (VPN, forecasting)
# ---------------------------------------------------------------------------

_vpn_manager: Any = None
_forecasting_engine: Any = None

# ---------------------------------------------------------------------------
# Hot loader (warmup / deadman retrigger)
# ---------------------------------------------------------------------------

try:
    from engine.hot_loader import CAIRRNHotLoader
    _hot_loader = CAIRRNHotLoader()
except Exception as _exc:
    startup_errors["hot_loader"] = str(_exc)
    print(f"[mcp_server._state] hot_loader init failed: {_exc}", file=sys.stderr)
    _hot_loader: Any = None

_retrigger_count: int = 0

# ---------------------------------------------------------------------------
# Adaptive CAIRRN state
# ---------------------------------------------------------------------------

_last_cairrn_coherence: float = 0.5


def set_cairrn_coherence(val: float) -> None:
    """Store the most recent CAIRRN-computed coherence score."""
    global _last_cairrn_coherence
    with _adaptive_lock:
        _last_cairrn_coherence = max(0.0, min(1.0, float(val)))


def _adaptive_confidence() -> float:
    """CAIRRN self-judged confidence — last hub-run coherence score [0, 1]."""
    with _adaptive_lock:
        return _last_cairrn_coherence


def _adaptive_consumption() -> float:
    """Mycelial credit activation — CODE hub shard energy (shards 3 + 4)."""
    if _harmonic_index is None:
        return 0.0
    shards = _harmonic_index.shards
    if len(shards) < 5:
        return 0.0
    return float(shards[3].activation + shards[4].activation)


def _get_vpn_manager() -> Any:
    """Return the live VPNManager, creating it on first call."""
    global _vpn_manager
    with _lazy_lock:
        if _vpn_manager is None:
            try:
                from pipeline.vpn.manager import VPNManager
                from pipeline.vpn.relay_pool import RelayPool
                _vpn_manager = VPNManager(pool=RelayPool())
            except Exception as exc:
                startup_errors["vpn_manager"] = str(exc)
                raise
        return _vpn_manager


def _get_forecasting_engine() -> Any:
    """Lazy-init the ForecastingEngine singleton (shares the global HarmonicIndex)."""
    global _forecasting_engine
    with _lazy_lock:
        if _forecasting_engine is None:
            if _harmonic_index is None:
                raise RuntimeError(
                    "forecasting engine unavailable: harmonic index failed to initialise"
                )
            from cognitive.forecasting_engine import ForecastingEngine
            _forecasting_engine = ForecastingEngine(_harmonic_index)
        return _forecasting_engine


# ---------------------------------------------------------------------------
# Harmonic snapshot persistence
# ---------------------------------------------------------------------------


def _snapshot_path() -> Path:
    """Canonical path, or the leftover nested path if that is the only file."""
    if _HARMONIC_SNAPSHOT.exists():
        return _HARMONIC_SNAPSHOT
    if _LEGACY_HARMONIC_SNAPSHOT.exists():
        return _LEGACY_HARMONIC_SNAPSHOT
    return _HARMONIC_SNAPSHOT


def restore_harmonic_snapshot() -> bool:
    """
    Load activations from disk into the live index.

    Returns True if a snapshot was applied. Silent on missing/corrupt files.
    """
    if _harmonic_index is None:
        return False
    path = _snapshot_path()
    if not path.exists():
        return False
    try:
        snap = json.loads(path.read_text())
        _harmonic_index.load_snapshot(snap)
        print(
            f"[mcp_server._state] harmonic snapshot restored "
            f"(step={_harmonic_index._step_count}, "
            f"total={_harmonic_index.total_activation():.4f})",
            file=sys.stderr,
        )
        return True
    except Exception as exc:
        print(
            f"[mcp_server._state] harmonic snapshot restore failed: {exc}",
            file=sys.stderr,
        )
        return False


def save_harmonic_snapshot() -> None:
    """
    Persist the current harmonic index activations to disk.

    Called after every mutation so the index survives server restarts.
    Never writes a cold ring — a dead snapshot would boot the next
    spawn into the same PSSPPS-flat state.
    Silent on failure.
    """
    if _harmonic_index is None:
        return
    if _harmonic_index.is_cold():
        return
    try:
        snap = _harmonic_index.dump_snapshot()
        _HARMONIC_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        _HARMONIC_SNAPSHOT.write_text(json.dumps(snap, indent=2))
    except Exception as exc:
        print(f"[mcp_server._state] harmonic snapshot save failed: {exc}", file=sys.stderr)


def ensure_harmonic_warm() -> bool:
    """
    Seed a HOME floor if the live ring is cold, then persist.

    Returns True if it injected. Call at gate-open so live-init and
    PSSPPS never see an all-zero activation vector.
    """
    if _harmonic_index is None:
        return False
    warmed = bool(_harmonic_index.ensure_warm())
    if warmed:
        print(
            f"[mcp_server._state] harmonic ring warmed "
            f"(total={_harmonic_index.total_activation():.4f}, "
            f"peak={_harmonic_index.peak_shard().index})",
            file=sys.stderr,
        )
        save_harmonic_snapshot()
    elif not _HARMONIC_SNAPSHOT.exists() and not _harmonic_index.is_cold():
        save_harmonic_snapshot()
    return warmed


restore_harmonic_snapshot()


# ---------------------------------------------------------------------------
# Stall callback + admission wiring (lazy — avoids circular imports)
# ---------------------------------------------------------------------------

def retrigger_warmups() -> None:
    """Deadman fire — delegates to _reinit.retrigger_warmups (lazy import avoids cycle)."""
    from mcp_server._reinit import retrigger_warmups as _fn
    _fn()


def _reinit_all_failed() -> dict[str, bool]:
    """Re-init all failed singletons — delegates to _reinit (lazy import avoids cycle)."""
    from mcp_server._reinit import _reinit_all_failed as _fn
    return _fn()


if not isinstance(_dom_queue, _NullDOMQueue):
    _dom_queue._on_stall = lambda _event: retrigger_warmups()  # type: ignore[attr-defined]

from mcp_server._admissions import wire_admissions as _wire_admissions  # noqa: E402

if not isinstance(_dom_queue, _NullDOMQueue):
    _wire_admissions(_dom_queue)
