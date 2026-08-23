"""
pipeline.vpn.mullvad — Mullvad CLI wrapper for the spotify-pipeline.

Three public entry points used by run.py:
    ensure_sweden()   — connect to a Swedish relay; idempotent
    allow_lan()       — permit LAN traffic while VPN is active
    socks5_proxy()    — return yt-dlp/requests proxy dict for the local SOCKS5 port

Root cause of the original DNS kill bug (2026-07-16):
    Mullvad's relay switching kills system DNS for 2-5s while rerouting.
    Spotify auth token refresh calls socket.getaddrinfo() during that window
    → socket.gaierror.  Fix lives in pipeline.auth._retry_network(), not here.
"""
from __future__ import annotations

import re
import socket
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

# ── constants ──────────────────────────────────────────────────────────────────
_MULLVAD: str = "mullvad"
SOCKS5_HOST: str = "127.0.0.1"
SOCKS5_PORT: int = 1080
_CONNECT_TIMEOUT: float = 30.0   # seconds to wait for Mullvad to report Connected
_POLL_INTERVAL: float = 1.0
_CLI_TIMEOUT: float = 10.0       # per-subprocess hard ceiling; prevents daemon hangs


# ── exceptions ─────────────────────────────────────────────────────────────────
class MullvadError(RuntimeError):
    """Raised when a Mullvad CLI call fails or times out."""


# ── data types ─────────────────────────────────────────────────────────────────
@dataclass
class RelayInfo:
    """Snapshot of the active Mullvad relay."""
    hostname: str
    city: str
    country: str
    ip: Optional[str] = field(default=None)

    def __str__(self) -> str:
        ip_part = f" ({self.ip})" if self.ip else ""
        return f"{self.hostname} in {self.city}, {self.country}{ip_part}"


# ── internal helpers ───────────────────────────────────────────────────────────
def _run(*args: str, check: bool = True, timeout: float = _CLI_TIMEOUT) -> subprocess.CompletedProcess[str]:
    """
    Run a mullvad subcommand, return CompletedProcess.

    Parameters
    ----------
    check   : raise MullvadError on non-zero exit (default True)
    timeout : hard ceiling per call in seconds (default 10s).
              Prevents indefinite blocks when the Mullvad daemon is unresponsive.
    """
    try:
        return subprocess.run(
            [_MULLVAD, *args],
            capture_output=True,
            text=True,
            check=check,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise MullvadError(
            "mullvad CLI not found — install Mullvad VPN and ensure 'mullvad' is on PATH"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise MullvadError(
            f"mullvad {' '.join(args)} timed out after {timeout}s — "
            "is the Mullvad daemon running? Try: sudo systemctl start mullvad-daemon"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise MullvadError(
            f"mullvad {' '.join(args)} failed (exit {exc.returncode}): {exc.stderr.strip()}"
        ) from exc


def _parse_relay_info(status_text: str) -> RelayInfo:
    """
    Parse hostname, city, IP from status output like:
        'Connected to se-sto-wg-204 in Stockholm, Sweden (89.37.63.206)'
    Returns a best-effort RelayInfo; fields default to 'unknown' on parse failure.
    """
    hostname = city = country = "unknown"
    ip: Optional[str] = None

    m_host = re.search(r"Connected to (\S+)", status_text)
    if m_host:
        hostname = m_host.group(1)

    m_loc = re.search(r"in ([^,(]+),\s*([^(]+)", status_text)
    if m_loc:
        city = m_loc.group(1).strip()
        country = m_loc.group(2).strip()

    m_ip = re.search(r"\((\d{1,3}(?:\.\d{1,3}){3})\)", status_text)
    if m_ip:
        ip = m_ip.group(1)

    return RelayInfo(hostname=hostname, city=city, country=country, ip=ip)


# ── public API ─────────────────────────────────────────────────────────────────
def status() -> str:
    """Return raw Mullvad status string (stdout + stderr)."""
    result = _run("status", check=False)
    return (result.stdout + result.stderr).strip()


def is_connected() -> bool:
    """True if Mullvad reports 'Connected'."""
    return "Connected" in status()


def ensure_sweden(timeout: float = _CONNECT_TIMEOUT) -> RelayInfo:
    """
    Connect to a Swedish relay; return RelayInfo.  Idempotent — safe to call
    repeatedly without triggering extra reconnections.

    Parameters
    ----------
    timeout : seconds to wait for Mullvad to report Connected (default 30)

    Raises
    ------
    MullvadError  if already connected to a non-Swedish relay and reconnect fails
    TimeoutError  if not Connected within `timeout` seconds
    """
    _run("relay", "set", "location", "se")

    current = status()
    # Already connected to Sweden → nothing to do
    if "Connected" in current and re.search(r"\bse-", current):
        return _parse_relay_info(current)

    _run("connect")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        st = status()
        if "Connected" in st:
            return _parse_relay_info(st)
        time.sleep(_POLL_INTERVAL)

    raise TimeoutError(
        f"Mullvad did not connect to Sweden within {timeout}s — last status: {status()}"
    )


def allow_lan() -> None:
    """Allow LAN traffic while the VPN tunnel is active."""
    _run("lan", "set", "allow")


def socks5_proxy() -> dict[str, str]:
    """
    Return a yt-dlp / requests -compatible SOCKS5 proxy dict.

    Mullvad exposes a local SOCKS5 proxy on 127.0.0.1:1080 when connected.
    Pass the returned dict as ``**socks5_proxy()`` to yt-dlp's ``--proxy`` arg
    or as the ``proxies`` kwarg to requests.

    Returns
    -------
    {"proxy": "socks5://127.0.0.1:1080"}
    """
    return {"proxy": f"socks5://{SOCKS5_HOST}:{SOCKS5_PORT}"}


def disconnect() -> None:
    """Disconnect Mullvad (best-effort — does not raise on failure)."""
    _run("disconnect", check=False)


def wait_for_socks5(timeout: float = 10.0) -> bool:
    """
    Poll until the local SOCKS5 port is reachable (indicates tunnel is live).

    Separate from is_connected() — the CLI may report Connected a second or two
    before the proxy port is actually bound.

    Returns True on success, False on timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((SOCKS5_HOST, SOCKS5_PORT), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.5)
    return False


# ── relay-specific connect ─────────────────────────────────────────────────────

def connect_relay(hostname: str, timeout: float = _CONNECT_TIMEOUT) -> RelayInfo:
    """
    Connect to a specific Mullvad relay by hostname.

    Parses the hostname (e.g. "se-sto-wg-004") to extract country and city,
    then runs:
        mullvad relay set location <cc> <city> <hostname>
        mullvad connect

    Parameters
    ----------
    hostname : relay hostname, e.g. "se-sto-wg-004"
    timeout  : seconds to wait for Connected state

    Returns
    -------
    RelayInfo of the connected relay

    Raises
    ------
    MullvadError  if the CLI call fails
    TimeoutError  if not Connected within `timeout` seconds
    """
    parts = hostname.split("-")
    if len(parts) < 3:
        raise MullvadError(f"Cannot parse relay hostname: {hostname!r}")
    country, city = parts[0], parts[1]

    _run("relay", "set", "location", country, city, hostname)
    _run("connect")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        st = status()
        if "Connected" in st:
            return _parse_relay_info(st)
        time.sleep(_POLL_INTERVAL)

    raise TimeoutError(
        f"Mullvad did not connect to {hostname!r} within {timeout}s — "
        f"last status: {status()}"
    )


# ── version detection + obfuscation ───────────────────────────────────────────

def detect_version() -> tuple[int, ...]:
    """
    Return the Mullvad version as an integer tuple, e.g. (2024, 3).

    Parses output from `mullvad version` or `mullvad --version`.
    Returns (0,) on parse failure so callers can safely do version >= (2023, 1).
    """
    for cmd in (["version"], ["--version"]):
        try:
            result = _run(*cmd, check=False)
            text = (result.stdout + result.stderr).strip()
            m = re.search(r"(\d{4})\.(\d+)", text)
            if m:
                return (int(m.group(1)), int(m.group(2)))
        except MullvadError:
            pass
    return (0,)


def apply_obfuscation(version: Optional[tuple[int, ...]] = None) -> str:
    """
    Apply the strongest available obfuscation mode for the installed version.

    Version gates:
        >= (2023, 1) — obfuscation auto  (Shadowsocks / WireGuard-over-TCP)
        >= (2024, 1) — DAITA also enabled (defense against traffic-analysis)

    Returns
    -------
    str describing what was applied: "daita+auto", "auto", or "none"
    """
    v = version if version is not None else detect_version()

    if v < (2023, 1):
        return "none"

    _run("obfuscation", "set", "auto", check=False)

    if v >= (2024, 1):
        # DAITA: adds dummy traffic + timing jitter to defeat shape-based fingerprinting
        _run("tunnel", "wireguard", "daita", "enable", check=False)
        return "daita+auto"

    return "auto"
