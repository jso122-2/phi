"""
pipeline.vpn.manager — VPNManager: full lifecycle, health monitoring, kill switch.

Architecture
------------
VPNManager is a thread-safe singleton that drives the complete VPN session:

    connect(relay=None)   pick relay from pool (or use explicit hostname),
                          apply obfuscation, connect, verify egress, record event
    verify()              re-run multi-endpoint egress consensus check
    rotate()              disconnect → pick new relay → connect + verify
    disconnect()          graceful teardown, clear state
    health_check()        one health cycle: verify if due, abort on leak

The manager maintains an alert ring buffer (last 20 events) that is the
primary monitoring surface exposed via the MCP vpn_state tool.

State machine
-------------
    DISCONNECTED → CONNECTING → VERIFYING → CONNECTED
                                                ↓
                                           ROTATING (relay swap in-progress)
                                                ↓
                                           VERIFYING → CONNECTED
    Any state → LEAKED   (egress check shows non-Mullvad IP)
    Any state → ERROR    (CLI failure or timeout)
"""
from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pipeline.vpn.egress import EgressResult, verify_egress
from pipeline.vpn.mullvad import (
    MullvadError,
    RelayInfo,
    allow_lan,
    apply_obfuscation,
    connect_relay,
    detect_version,
    disconnect,
    is_connected,
    wait_for_socks5,
)
from pipeline.vpn.relay_pool import RelayPool

_ALERT_RING_SIZE = 20
_HEALTH_VERIFY_INTERVAL_S = 30.0   # seconds between background health checks
_SOCKS5_WAIT_TIMEOUT_S = 15.0
_EGRESS_TIMEOUT_S = 12.0


# ── status enum ───────────────────────────────────────────────────────────────

class VPNStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING   = "connecting"
    VERIFYING    = "verifying"
    CONNECTED    = "connected"
    ROTATING     = "rotating"
    LEAKED       = "leaked"
    ERROR        = "error"


# ── manager ───────────────────────────────────────────────────────────────────

class VPNManager:
    """
    Thread-safe VPN lifecycle manager.

    Parameters
    ----------
    pool              : RelayPool to draw relays from (default: EU pool)
    allow_lan_on_connect : run `mullvad lan set allow` after each connect
    auto_obfuscate    : detect version and apply best obfuscation on connect
    health_interval_s : seconds between background egress re-checks
    """

    def __init__(
        self,
        pool: Optional[RelayPool] = None,
        allow_lan_on_connect: bool = True,
        auto_obfuscate: bool = True,
        health_interval_s: float = _HEALTH_VERIFY_INTERVAL_S,
    ) -> None:
        self._pool = pool or RelayPool()
        self._allow_lan_on_connect = allow_lan_on_connect
        self._auto_obfuscate = auto_obfuscate
        self._health_interval_s = health_interval_s

        self._lock = threading.RLock()  # re-entrant: state_dict() may be called while locked
        self._status = VPNStatus.DISCONNECTED
        self._relay: Optional[RelayInfo] = None
        self._egress: Optional[EgressResult] = None
        self._obfuscation: str = "none"
        self._mullvad_version: tuple[int, ...] = (0,)
        self._last_verify_utc: Optional[str] = None
        self._last_health_check_utc: Optional[str] = None
        self._error: Optional[str] = None

        self._alerts: deque[dict[str, Any]] = deque(maxlen=_ALERT_RING_SIZE)
        self._health_thread_running = False

    # ── public API ─────────────────────────────────────────────────────────────

    def connect(self, relay: Optional[str] = None) -> dict[str, Any]:
        """
        Connect to the VPN.

        Parameters
        ----------
        relay : explicit relay hostname (e.g. "se-sto-wg-004").
                If None, picks randomly from the pool.

        Returns
        -------
        State dict (same as state_dict())

        Raises
        ------
        MullvadError  if CLI call fails
        TimeoutError  if connection does not establish in time
        RuntimeError  if egress verification fails (leak detected)
        """
        with self._lock:
            self._set_status(VPNStatus.CONNECTING)
            self._error = None

        try:
            chosen = relay or self._pool.pick()

            # version-detect once per session
            version = detect_version()
            with self._lock:
                self._mullvad_version = version

            # apply obfuscation before connecting
            if self._auto_obfuscate:
                obf = apply_obfuscation(version)
                with self._lock:
                    self._obfuscation = obf

            relay_info = connect_relay(chosen)

            if self._allow_lan_on_connect:
                allow_lan()

            # wait for SOCKS5 port to bind
            if not wait_for_socks5(timeout=_SOCKS5_WAIT_TIMEOUT_S):
                raise MullvadError(
                    f"SOCKS5 port did not bind within {_SOCKS5_WAIT_TIMEOUT_S}s "
                    f"after connecting to {chosen}"
                )

            with self._lock:
                self._relay = relay_info
                self._set_status(VPNStatus.VERIFYING)

            self._record("connecting", relay=chosen)

        except Exception as exc:
            with self._lock:
                self._error = str(exc)
                self._set_status(VPNStatus.ERROR)
            self._record("connect_error", error=str(exc))
            raise

        # egress verification — outside the broad except so leak errors propagate
        egress = verify_egress(
            proxy=f"socks5://127.0.0.1:1080",
            timeout=_EGRESS_TIMEOUT_S,
        )

        with self._lock:
            self._egress = egress
            self._last_verify_utc = _utc_now()

        if not egress.consensus_ok:
            with self._lock:
                self._set_status(VPNStatus.LEAKED)
                self._error = f"Egress consensus failed: {egress}"
            self._record("leak_detected", egress=egress.to_dict())
            raise RuntimeError(f"VPN egress leak detected — aborting. {egress}")

        with self._lock:
            self._set_status(VPNStatus.CONNECTED)

        self._record("connected", relay=str(relay_info), egress_ip=egress.consensus_ip)
        return self.state_dict()

    def verify(self) -> dict[str, Any]:
        """
        Re-run egress consensus check immediately.

        Updates internal state; raises RuntimeError on leak.
        """
        with self._lock:
            if self._status not in (VPNStatus.CONNECTED, VPNStatus.VERIFYING):
                return self.state_dict()

        egress = verify_egress(proxy="socks5://127.0.0.1:1080", timeout=_EGRESS_TIMEOUT_S)
        now = _utc_now()

        with self._lock:
            self._egress = egress
            self._last_verify_utc = now
            self._last_health_check_utc = now

        if not egress.consensus_ok:
            with self._lock:
                self._set_status(VPNStatus.LEAKED)
                self._error = f"Egress consensus failed: {egress}"
            self._record("leak_detected", egress=egress.to_dict())
            raise RuntimeError(f"VPN egress leak: {egress}")

        self._record("verify_ok", egress_ip=egress.consensus_ip)
        return self.state_dict()

    def rotate(self, relay: Optional[str] = None) -> dict[str, Any]:
        """
        Rotate to a new relay: disconnect → pick → connect + verify.

        Parameters
        ----------
        relay : explicit target relay; if None, pool.pick() is used

        Returns
        -------
        State dict after successful reconnect
        """
        old_relay = None
        with self._lock:
            if self._relay:
                old_relay = self._relay.hostname
            self._set_status(VPNStatus.ROTATING)

        try:
            disconnect()
        except Exception:
            pass  # best-effort; proceed with reconnect regardless

        new_relay = relay or self._pool.pick()
        self._record("rotating", from_relay=old_relay, to_relay=new_relay)

        return self.connect(relay=new_relay)

    def disconnect(self) -> dict[str, Any]:
        """Disconnect the VPN and clear state."""
        try:
            disconnect()
        except Exception as exc:
            self._record("disconnect_error", error=str(exc))

        with self._lock:
            self._relay = None
            self._egress = None
            self._set_status(VPNStatus.DISCONNECTED)

        self._record("disconnected")
        return self.state_dict()

    def health_check(self) -> dict[str, Any]:
        """
        One health monitoring cycle.

        Called by the background thread in server.py.  Only runs a verify
        if the tunnel is CONNECTED and enough time has passed since the last check.

        Does NOT raise — all errors are recorded in the alert ring and surfaced
        via state_dict().  On a confirmed leak, status transitions to LEAKED.
        """
        with self._lock:
            status = self._status
            last_check = self._last_health_check_utc

        if status != VPNStatus.CONNECTED:
            return self.state_dict()

        # throttle: only verify if the interval has elapsed
        if last_check is not None:
            import time
            # last_check is ISO UTC; compare via monotonic approximation
            # stored as side-channel on the object
            elapsed = getattr(self, "_last_health_monotonic", 0.0)
            now_mono = time.monotonic()
            if (now_mono - elapsed) < self._health_interval_s:
                return self.state_dict()

        import time
        self._last_health_monotonic = time.monotonic()

        try:
            return self.verify()
        except RuntimeError:
            # leak already recorded in verify(); return degraded state
            return self.state_dict()
        except Exception as exc:
            with self._lock:
                self._error = str(exc)
            self._record("health_check_error", error=str(exc))
            return self.state_dict()

    # ── state ──────────────────────────────────────────────────────────────────

    def state_dict(self) -> dict[str, Any]:
        """Return a fully serialisable snapshot of current VPN state."""
        with self._lock:
            relay = self._relay
            egress = self._egress
            return {
                "status": self._status.value,
                "relay": relay.hostname if relay else None,
                "city": relay.city if relay else None,
                "country": relay.country if relay else None,
                "egress_ip": egress.consensus_ip if egress else None,
                "egress_verified": egress.consensus_ok if egress else False,
                "mullvad_confirmed": egress.mullvad_confirmed if egress else False,
                "last_verify_utc": self._last_verify_utc,
                "last_health_check_utc": self._last_health_check_utc,
                "obfuscation": self._obfuscation,
                "mullvad_version": ".".join(str(p) for p in self._mullvad_version),
                "pool_size": self._pool.size,
                "pool_history": self._pool.history,
                "error": self._error,
                "alert_ring": list(self._alerts),
                "socks5_proxy": "socks5://127.0.0.1:1080",
            }

    # ── internals ──────────────────────────────────────────────────────────────

    def _set_status(self, status: VPNStatus) -> None:
        """Set status — caller must hold self._lock."""
        self._status = status

    def _record(self, event: str, **kwargs: Any) -> None:
        """Append an event to the alert ring."""
        entry: dict[str, Any] = {"ts": _utc_now(), "event": event}
        entry.update(kwargs)
        with self._lock:
            self._alerts.append(entry)


# ── utilities ─────────────────────────────────────────────────────────────────

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
