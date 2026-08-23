"""
pipeline.vpn — Mullvad VPN management.

Public surface
--------------
VPNManager   — high-level lifecycle manager (connect, verify, rotate, disconnect)
RelayPool    — EU relay pool with history-aware random selection
EgressResult — result type from verify_egress()
verify_egress — run multi-endpoint consensus egress check directly

Low-level (mullvad.py) exports retained for backwards compat with run.py:
MullvadError, RelayInfo, allow_lan, disconnect, ensure_sweden,
is_connected, socks5_proxy, status
"""
from pipeline.vpn.egress import EgressResult, verify_egress
from pipeline.vpn.manager import VPNManager, VPNStatus
from pipeline.vpn.mullvad import (
    MullvadError,
    RelayInfo,
    allow_lan,
    disconnect,
    ensure_sweden,
    is_connected,
    socks5_proxy,
    status,
)
from pipeline.vpn.relay_pool import RelayPool

__all__ = [
    # high-level
    "VPNManager",
    "VPNStatus",
    "RelayPool",
    "EgressResult",
    "verify_egress",
    # low-level (backwards compat)
    "MullvadError",
    "RelayInfo",
    "allow_lan",
    "disconnect",
    "ensure_sweden",
    "is_connected",
    "socks5_proxy",
    "status",
]
