"""
mcp_server.tools.vpn — VPN lifecycle tools.

Five MCP tools that expose VPNManager through the standard gate pattern:

    vpn_state      — snapshot + alert ring; init-free (readable at any time)
    vpn_connect    — connect to a relay, apply obfuscation, verify egress
    vpn_verify     — re-run egress consensus check immediately
    vpn_rotate     — disconnect → pick new relay → connect + verify
    vpn_disconnect — graceful teardown

Failure monitoring
------------------
All failures are recorded in the manager's alert ring buffer (last 20 events)
and returned by every tool call via the "alert_ring" key.  Critical failures
(leak, CLI error) are also written to mcp_server._state.startup_errors["vpn_*"]
so they surface in init_check() / system_status() without a dedicated VPN call.
"""
from __future__ import annotations

from typing import Any, Optional

from mcp_server._gate import requires_init
from mcp_server._state import _dom_queue, _get_vpn_manager, mcp, startup_errors


# ── helpers ───────────────────────────────────────────────────────────────────

def _mgr() -> Any:
    """Return the VPNManager singleton, creating it if needed."""
    return _get_vpn_manager()


def _surface_error(key: str, message: str) -> None:
    """Write a critical error into startup_errors so system_status picks it up."""
    startup_errors[key] = message


def _clear_error(key: str) -> None:
    startup_errors.pop(key, None)


# ── tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def vpn_state() -> dict[str, Any]:
    """
    Return the current VPN state snapshot and alert ring.

    Init-free — can be called at any time to check VPN health, even before
    session initialisation or if another component has failed.

    Returns
    -------
    dict with keys: status, relay, city, country, egress_ip, egress_verified,
    mullvad_confirmed, last_verify_utc, obfuscation, mullvad_version,
    pool_size, pool_history, error, alert_ring, socks5_proxy
    """
    with _dom_queue.gate("vpn_state"):
        import mcp_server._state as _st
        if _st._vpn_manager is None:
            return {
                "status": "disconnected",
                "relay": None,
                "egress_ip": None,
                "egress_verified": False,
                "mullvad_confirmed": False,
                "obfuscation": "none",
                "mullvad_version": "unknown",
                "pool_size": 0,
                "pool_history": [],
                "error": None,
                "alert_ring": [],
                "socks5_proxy": "socks5://127.0.0.1:1080",
                "note": "VPN manager not yet initialised — call vpn_connect to start",
            }
        return _mgr().state_dict()


@mcp.tool()
@requires_init
def vpn_connect(relay: Optional[str] = None) -> dict[str, Any]:
    """
    Connect to the VPN.

    Sequence: pick relay from EU pool → apply obfuscation (auto-detected) →
    connect via Mullvad CLI → wait for SOCKS5 → verify egress via 3 endpoints →
    record result in alert ring.

    Parameters
    ----------
    relay : optional explicit relay hostname, e.g. "se-sto-wg-004".
            If omitted, a random relay is picked from the EU pool (SE/NL/DE),
            excluding the last 2 used relays.

    Returns
    -------
    VPN state dict.  On failure, "error" key contains the reason.
    """
    with _dom_queue.gate("vpn_connect"):
        try:
            result = _mgr().connect(relay=relay)
            _clear_error("vpn_connect")
            return result
        except Exception as exc:
            msg = str(exc)
            _surface_error("vpn_connect", msg)
            return {"error": msg, "status": "error"}


@mcp.tool()
@requires_init
def vpn_verify() -> dict[str, Any]:
    """
    Re-run egress consensus check right now.

    Queries am.i.mullvad.net, icanhazip.com, and api.ipify.org in parallel.
    Requires 2/3 agreement on the public IP.  Mullvad's endpoint must
    confirm mullvad_exit_ip=true for full verification.

    Returns
    -------
    VPN state dict with updated egress fields.  Sets status to "leaked" and
    records to startup_errors if the check fails.
    """
    with _dom_queue.gate("vpn_verify"):
        try:
            result = _mgr().verify()
            _clear_error("vpn_leak")
            return result
        except RuntimeError as exc:
            msg = str(exc)
            _surface_error("vpn_leak", msg)
            return {"error": msg, "status": "leaked"}
        except Exception as exc:
            msg = str(exc)
            _surface_error("vpn_verify", msg)
            return {"error": msg, "status": "error"}


@mcp.tool()
@requires_init
def vpn_rotate(relay: Optional[str] = None) -> dict[str, Any]:
    """
    Rotate to a new relay.

    Sequence: disconnect → pick new relay (excluding recent history) →
    connect + verify egress.

    Parameters
    ----------
    relay : optional explicit target relay hostname.
            If omitted, the pool picks a new relay avoiding the last 2 used.

    Returns
    -------
    VPN state dict after successful reconnect.
    """
    with _dom_queue.gate("vpn_rotate"):
        try:
            result = _mgr().rotate(relay=relay)
            _clear_error("vpn_connect")
            _clear_error("vpn_leak")
            return result
        except Exception as exc:
            msg = str(exc)
            _surface_error("vpn_rotate", msg)
            return {"error": msg, "status": "error"}


@mcp.tool()
@requires_init
def vpn_disconnect() -> dict[str, Any]:
    """
    Disconnect the VPN and clear state.

    Best-effort — does not raise on CLI failure (failure recorded in alert ring).

    Returns
    -------
    VPN state dict with status "disconnected".
    """
    with _dom_queue.gate("vpn_disconnect"):
        import mcp_server._state as _st
        if _st._vpn_manager is None:
            return {"status": "disconnected", "note": "VPN was not connected"}
        result = _mgr().disconnect()
        _clear_error("vpn_connect")
        _clear_error("vpn_leak")
        return result
