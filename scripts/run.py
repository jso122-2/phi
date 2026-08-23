"""
run.py — spotify-pipeline entry point.

Usage
-----
    python run.py                  # full run: VPN + fetch + download
    python run.py --no-vpn         # skip Mullvad setup (dev / CI)
    python run.py --config path/to/config.yaml

VPN sequence (when enabled)
----------------------------
    _setup_vpn(cfg)       connect to Mullvad Sweden, allow LAN
    _wait_for_dns(cfg)    wait until DNS resolves (2-5s window after relay switch)
    run_workers(...)      parallel downloads via yt-dlp through SOCKS5 proxy
"""
from __future__ import annotations

import argparse
import logging
import socket
import sys
import time
from pathlib import Path
from typing import Any

from pipeline.utils.config import Config, load_config
from pipeline.vpn.mullvad import MullvadError, RelayInfo, allow_lan, ensure_sweden

log = logging.getLogger(__name__)

_DEFAULT_CONFIG = Path(__file__).parent.parent / "config" / "config.yaml"


# ── VPN helpers ────────────────────────────────────────────────────────────────
def _setup_vpn(cfg: Config) -> RelayInfo:
    """
    Connect to Mullvad Sweden and enable LAN.

    Reads from cfg.vpn:
        country          — 'sweden' (passed to ensure_sweden via relay location)
        connect_timeout_s
        allow_lan

    Returns
    -------
    RelayInfo of the connected relay

    Raises
    ------
    MullvadError  if the Mullvad CLI is unavailable or connect fails
    TimeoutError  if connection doesn't establish within connect_timeout_s
    """
    timeout = float(cfg.get("vpn", "connect_timeout_s") or 30)
    log.info("VPN: connecting to Mullvad Sweden (timeout=%.0fs)…", timeout)

    relay = ensure_sweden(timeout=timeout)
    log.info("VPN: connected → %s", relay)

    if cfg.get("vpn", "allow_lan"):
        allow_lan()
        log.debug("VPN: LAN access allowed")

    return relay


_DNS_PROBE_TIMEOUT: float = 5.0    # per-probe TCP connect timeout (avoids getaddrinfo hanging)
_DNS_PROBE_PORT: int = 443         # HTTPS — confirms DNS + basic reachability


def _wait_for_dns(
    cfg: Config,
    *,
    host: str | None = None,
    timeout: float | None = None,
    interval: float | None = None,
) -> None:
    """
    Block until the warmup host is DNS-resolvable and TCP-reachable, or raise TimeoutError.

    This is the DNS warmup gate that prevents socket.gaierror during the
    2-5s blackout that Mullvad creates when switching relays.

    Implementation note — why not socket.getaddrinfo():
        getaddrinfo() has no timeout parameter.  On macOS the system resolver
        can block for 30+ seconds per call, silently extending the total wall
        time far beyond `timeout`.  Instead we use socket.create_connection()
        with an explicit timeout=5s — this both resolves DNS AND verifies
        the tunnel is routing traffic.

    Parameters
    ----------
    cfg      : pipeline Config (reads vpn.dns_warmup_* keys)
    host     : override the config host
    timeout  : override the config timeout_s
    interval : override the config interval_s

    Raises
    ------
    TimeoutError if the host is not reachable within `timeout` seconds
    """
    _host = host or str(cfg.get("vpn", "dns_warmup_host") or "open.spotify.com")
    _timeout = float(timeout if timeout is not None else (cfg.get("vpn", "dns_warmup_timeout_s") or 60))
    _interval = float(interval if interval is not None else (cfg.get("vpn", "dns_warmup_interval_s") or 1))

    log.info("DNS warmup: probing %r:%d (budget=%.0fs, probe_timeout=%.0fs)…",
             _host, _DNS_PROBE_PORT, _timeout, _DNS_PROBE_TIMEOUT)
    deadline = time.monotonic() + _timeout
    attempts = 0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((_host, _DNS_PROBE_PORT), timeout=_DNS_PROBE_TIMEOUT):
                log.info("DNS warmup: %r reachable after %d attempt(s)", _host, attempts + 1)
                return
        except OSError:
            attempts += 1
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(_interval, remaining))

    raise TimeoutError(
        f"DNS warmup: {_host!r}:{_DNS_PROBE_PORT} not reachable within {_timeout}s "
        f"({attempts} attempt(s)) — is Mullvad routing traffic?"
    )


def _worker_kwargs(cfg: Config, *, vpn_active: bool | None = None) -> dict[str, Any]:
    """
    Build the kwargs dict injected into each worker / yt-dlp call.

    Parameters
    ----------
    cfg        : pipeline Config
    vpn_active : explicit override for whether the proxy should be injected.
                 Defaults to cfg.vpn.enabled when None.
                 Pass False when --no-vpn is used so the proxy is not injected
                 even though config.yaml still has vpn.enabled=true.

    Returns
    -------
    dict with keys: proxy (str | None), n_threads (int), retry_passes (int),
    pass_delays_s (list[int]), pass_timeout_s (int)
    """
    use_vpn: bool = vpn_active if vpn_active is not None else bool(cfg.get("vpn", "enabled"))
    socks5_host: str = str(cfg.get("vpn", "socks5", "host") or "127.0.0.1")
    socks5_port: int = int(cfg.get("vpn", "socks5", "port") or 1080)
    proxy: str | None = (
        f"socks5://{socks5_host}:{socks5_port}" if use_vpn else None
    )

    return {
        "proxy": proxy,
        "n_threads": int(cfg.get("workers", "n_threads") or 4),
        "retry_passes": int(cfg.get("workers", "retry_passes") or 3),
        "pass_delays_s": list(cfg.get("workers", "pass_delays_s") or [20, 90]),
        "pass_timeout_s": int(cfg.get("workers", "pass_timeout_s") or 600),
    }


# ── entry point ────────────────────────────────────────────────────────────────
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="spotify-pipeline download runner")
    p.add_argument(
        "--config", type=Path, default=_DEFAULT_CONFIG,
        help="Path to config.yaml (default: config/config.yaml)",
    )
    p.add_argument(
        "--no-vpn", action="store_true",
        help="Skip Mullvad VPN setup (useful for dev/CI without Mullvad installed)",
    )
    p.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    cfg = load_config(args.config)
    vpn_enabled = bool(cfg.get("vpn", "enabled")) and not args.no_vpn

    # ── VPN setup ──────────────────────────────────────────────────────────────
    if vpn_enabled:
        try:
            _setup_vpn(cfg)
            _wait_for_dns(cfg)
        except MullvadError as exc:
            log.error("VPN setup failed: %s", exc)
            return 1
        except TimeoutError as exc:
            log.error("Timeout: %s", exc)
            return 1
    else:
        log.info("VPN disabled — running without Mullvad")

    # vpn_active=vpn_enabled ensures --no-vpn clears the proxy even if
    # config.yaml still has vpn.enabled=true
    worker_kwargs = _worker_kwargs(cfg, vpn_active=vpn_enabled)
    log.debug("Worker kwargs: %s", worker_kwargs)

    from pipeline.worker import run_workers
    from pipeline.sources import DEFAULT_SOURCES
    from pipeline.sources.soundcloud import SoundCloudSource
    from pipeline.sources.internet_archive import InternetArchiveSource
    from pipeline.sources.youtube_music import YouTubeMusicSource
    from pipeline.sources.youtube import YouTubeSource

    # Build source list from config priority; respect per-source proxy settings.
    # youtube_music and youtube route through the VPN proxy when enabled.
    # soundcloud and internet_archive use direct connections per config.
    proxy = worker_kwargs.get("proxy")
    _src_cfg = cfg.get("sources") or {}

    def _src_proxy(name: str) -> str | None:
        """Return proxy for *name* if config says use_proxy=true, else None."""
        if not proxy:
            return None
        return proxy if (_src_cfg.get(name) or {}).get("use_proxy") else None

    source_map = {
        "youtube_music":    (YouTubeMusicSource(),    _src_proxy("youtube_music")),
        "youtube":          (YouTubeSource(),         _src_proxy("youtube")),
        "soundcloud":       (SoundCloudSource(),      _src_proxy("soundcloud")),
        "internet_archive": (InternetArchiveSource(), _src_proxy("internet_archive")),
    }

    priority = (_src_cfg.get("priority") or []) or [
        "youtube_music", "youtube", "soundcloud", "internet_archive"
    ]
    sources = [source_map[n][0] for n in priority if n in source_map]

    if not sources:
        log.error("No download sources configured — check config.yaml sources.priority")
        return 1

    log.info("Sources: %s", [s.name for s in sources])
    log.info("Pipeline ready — fetcher not yet wired; pass jobs manually or run fetcher separately")
    return 0


if __name__ == "__main__":
    sys.exit(main())
