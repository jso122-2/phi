"""
pipeline.vpn.egress — multi-endpoint consensus egress IP verification.

Queries three independent endpoints in parallel, requires 2/3 majority
agreement on the returned public IP.  The Mullvad endpoint additionally
confirms the IP is a known Mullvad exit node via the `mullvad_exit_ip` flag.

Endpoints
---------
1. https://am.i.mullvad.net/json   — ASN, relay name, mullvad_exit_ip bool
2. https://icanhazip.com           — bare IP string, no JS, fastest
3. https://api.ipify.org?format=json — neutral JSON {"ip": "..."}

Usage
-----
    result = verify_egress(proxy="socks5://127.0.0.1:1080", timeout=10.0)
    if not result.consensus_ok:
        raise RuntimeError(f"Egress leak: {result}")
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

_ENDPOINTS: list[str] = [
    "https://am.i.mullvad.net/json",
    "https://icanhazip.com",
    "https://api.ipify.org?format=json",
]

_REQUIRED_AGREEMENT: int = 2  # out of 3 endpoints must agree


# ── result type ───────────────────────────────────────────────────────────────

@dataclass
class EgressResult:
    """
    Result of a multi-endpoint egress verification.

    Attributes
    ----------
    consensus_ip      : the IP that ≥2 endpoints agreed on (None = no consensus)
    consensus_ok      : True if ≥2/3 endpoints agree on the same IP
    mullvad_confirmed : am.i.mullvad.net confirmed mullvad_exit_ip = true
    responses         : endpoint URL → returned IP string or "ERROR: ..."
    raw_mullvad       : full JSON dict from am.i.mullvad.net (empty on failure)
    """

    consensus_ip: Optional[str]
    consensus_ok: bool
    mullvad_confirmed: bool
    responses: dict[str, str]
    raw_mullvad: dict = field(default_factory=dict)

    def __str__(self) -> str:
        status = "OK" if self.consensus_ok else "FAILED"
        mv = " [mullvad-confirmed]" if self.mullvad_confirmed else " [NOT-mullvad]"
        return (
            f"EgressResult({status} ip={self.consensus_ip}{mv} "
            f"responses={self.responses})"
        )

    def to_dict(self) -> dict:
        return {
            "consensus_ip": self.consensus_ip,
            "consensus_ok": self.consensus_ok,
            "mullvad_confirmed": self.mullvad_confirmed,
            "responses": self.responses,
            "mullvad_server": self.raw_mullvad.get("mullvad_server"),
            "mullvad_city": self.raw_mullvad.get("city"),
            "mullvad_country": self.raw_mullvad.get("country"),
        }


# ── internal fetch ─────────────────────────────────────────────────────────────

def _fetch_ip(url: str, proxy: Optional[str], timeout: float) -> tuple[str, str, dict]:
    """
    Fetch the public IP from one endpoint.

    Returns
    -------
    (url, ip_string, raw_dict)

    Raises on any error so the ThreadPoolExecutor can capture it.
    """
    handler_list: list = []
    if proxy:
        handler_list.append(
            urllib.request.ProxyHandler({"https": proxy, "http": proxy})
        )
    opener = urllib.request.build_opener(*handler_list)
    req = urllib.request.Request(url, headers={"User-Agent": "curl/7.88.1"})

    with opener.open(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8").strip()

    raw: dict = {}
    ip: str

    if "mullvad" in url:
        raw = json.loads(body)
        ip = raw.get("ip", "")
    elif "ipify" in url:
        raw = json.loads(body)
        ip = raw.get("ip", "")
    else:
        ip = body  # icanhazip returns a bare IP

    if not ip:
        raise ValueError(f"Empty IP returned from {url}")

    return url, ip, raw


# ── public API ─────────────────────────────────────────────────────────────────

def verify_egress(
    proxy: Optional[str] = None,
    timeout: float = 10.0,
    endpoints: Optional[list[str]] = None,
) -> EgressResult:
    """
    Query all endpoints in parallel and return a consensus egress result.

    Parameters
    ----------
    proxy     : SOCKS5 proxy URL to route requests through, e.g. "socks5://127.0.0.1:1080"
                Pass None to check without a proxy (useful for pre-connect sanity checks).
    timeout   : per-endpoint HTTP timeout in seconds
    endpoints : override the default endpoint list

    Returns
    -------
    EgressResult with:
        consensus_ok=True  if ≥2/3 endpoints agree on the same IP
        mullvad_confirmed  True if Mullvad's own endpoint confirms the IP is theirs
    """
    targets = endpoints if endpoints is not None else _ENDPOINTS
    responses: dict[str, str] = {}
    raw_mullvad: dict = {}
    mullvad_confirmed = False

    with ThreadPoolExecutor(max_workers=len(targets), thread_name_prefix="egress") as pool:
        futures = {
            pool.submit(_fetch_ip, url, proxy, timeout): url
            for url in targets
        }
        for fut in as_completed(futures):
            url = futures[fut]
            try:
                _, ip, raw = fut.result()
                responses[url] = ip
                if "mullvad" in url:
                    raw_mullvad = raw
                    mullvad_confirmed = bool(raw.get("mullvad_exit_ip", False))
            except Exception as exc:
                responses[url] = f"ERROR: {exc}"

    valid_ips = [v for v in responses.values() if not v.startswith("ERROR")]

    if not valid_ips:
        return EgressResult(
            consensus_ip=None,
            consensus_ok=False,
            mullvad_confirmed=False,
            responses=responses,
            raw_mullvad=raw_mullvad,
        )

    counts = Counter(valid_ips)
    top_ip, top_count = counts.most_common(1)[0]
    consensus_ok = top_count >= _REQUIRED_AGREEMENT

    return EgressResult(
        consensus_ip=top_ip if consensus_ok else None,
        consensus_ok=consensus_ok,
        mullvad_confirmed=mullvad_confirmed,
        responses=responses,
        raw_mullvad=raw_mullvad,
    )
