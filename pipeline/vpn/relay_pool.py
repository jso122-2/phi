"""
pipeline.vpn.relay_pool — EU relay pool for defensive VPN rotation.

Maintains a weighted pool of Mullvad relay hostnames across SE/NL/DE.
Random selection excludes the last N used relays (configurable) to
prevent back-to-back repeats.

The default pool is hard-coded from the Mullvad WireGuard relay list (2024).
Call `pool.refresh()` to repopulate live from `mullvad relay list` output.
"""
from __future__ import annotations

import re
import subprocess
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

# Country codes included in the EU pool; all have good YouTube Music coverage
_POOL_COUNTRIES: frozenset[str] = frozenset({"se", "nl", "de"})

# Hostname pattern produced by `mullvad relay list`
_RELAY_PATTERN = re.compile(r"\b([a-z]{2}-[a-z]{3}-wg-\d{3})\b")

# Hard-coded 2024 baseline; `refresh()` replaces this at runtime
_DEFAULT_POOL: list[str] = [
    # Sweden — primary (best YouTube Music regional availability)
    "se-got-wg-001", "se-got-wg-002",
    "se-mma-wg-001", "se-mma-wg-002",
    "se-sto-wg-001", "se-sto-wg-002", "se-sto-wg-003", "se-sto-wg-004",
    # Netherlands — secondary
    "nl-ams-wg-001", "nl-ams-wg-002", "nl-ams-wg-003",
    "nl-rot-wg-001", "nl-rot-wg-002",
    # Germany — tertiary
    "de-ber-wg-001", "de-ber-wg-002",
    "de-fra-wg-001", "de-fra-wg-002", "de-fra-wg-003",
    "de-muc-wg-001",
]


@dataclass
class RelayPool:
    """
    Rotating pool of EU Mullvad relay hostnames.

    Parameters
    ----------
    relays       : initial relay list; defaults to _DEFAULT_POOL
    history_size : number of recently-used relays excluded from next pick (default 2)
    """

    relays: list[str] = field(default_factory=lambda: list(_DEFAULT_POOL))
    history_size: int = 2

    _history: deque[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._history = deque(maxlen=self.history_size)

    # ── selection ──────────────────────────────────────────────────────────────

    def pick(self) -> str:
        """
        Pick a random relay, excluding the last `history_size` used.

        Falls back to the full pool if all relays are in history (tiny pool edge case).

        Returns
        -------
        hostname string, e.g. "se-sto-wg-004"
        """
        import random
        available = [r for r in self.relays if r not in self._history]
        if not available:
            available = list(self.relays)
        chosen = random.choice(available)
        self._history.append(chosen)
        return chosen

    # ── helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def country_code(hostname: str) -> str:
        """Extract two-letter country code, e.g. "se-sto-wg-004" → "se"."""
        return hostname.split("-")[0] if hostname else "unknown"

    @staticmethod
    def city_code(hostname: str) -> str:
        """Extract three-letter city code, e.g. "se-sto-wg-004" → "sto"."""
        parts = hostname.split("-")
        return parts[1] if len(parts) > 1 else "unknown"

    # ── live refresh ───────────────────────────────────────────────────────────

    def refresh(self, timeout: float = 15.0) -> int:
        """
        Repopulate relay list from `mullvad relay list` output.

        Filters to WireGuard relays in _POOL_COUNTRIES.
        Falls back silently to the existing list if the CLI call fails.

        Returns
        -------
        int — number of relays loaded from the CLI (0 = fallback still active)
        """
        try:
            result = subprocess.run(
                ["mullvad", "relay", "list"],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            found = _RELAY_PATTERN.findall(result.stdout)
            eu_relays = [
                r for r in found
                if r.split("-")[0] in _POOL_COUNTRIES
            ]
            if eu_relays:
                self.relays = eu_relays
                return len(eu_relays)
        except Exception:
            pass
        return 0

    # ── properties ─────────────────────────────────────────────────────────────

    @property
    def size(self) -> int:
        return len(self.relays)

    @property
    def last_used(self) -> Optional[str]:
        return self._history[-1] if self._history else None

    @property
    def history(self) -> list[str]:
        return list(self._history)
