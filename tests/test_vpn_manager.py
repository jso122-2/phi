"""
Tests for the defensive VPN layer:
    pipeline.vpn.relay_pool  — RelayPool selection and refresh
    pipeline.vpn.egress      — EgressResult, verify_egress consensus
    pipeline.vpn.manager     — VPNManager lifecycle and state machine

All tests are fully offline — Mullvad CLI and network calls are mocked.
"""
from __future__ import annotations

import json
from collections import deque
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pipeline.vpn.egress import EgressResult, verify_egress, _fetch_ip
from pipeline.vpn.manager import VPNManager, VPNStatus, _utc_now
from pipeline.vpn.relay_pool import RelayPool


# ══════════════════════════════════════════════════════════════════════════════
# RelayPool
# ══════════════════════════════════════════════════════════════════════════════

class TestRelayPool:
    def test_pick_returns_pool_member(self):
        pool = RelayPool(relays=["se-sto-wg-001", "nl-ams-wg-001", "de-ber-wg-001"])
        chosen = pool.pick()
        assert chosen in pool.relays

    def test_pick_excludes_recent_history(self):
        relays = [f"se-sto-wg-{i:03d}" for i in range(10)]
        pool = RelayPool(relays=relays, history_size=2)
        picks = [pool.pick() for _ in range(30)]
        # Each pick must not match either of the 2 immediately preceding picks
        for i in range(2, len(picks)):
            assert picks[i] != picks[i - 1], (
                f"pick[{i}]={picks[i]} repeated pick[{i-1}]"
            )
            assert picks[i] != picks[i - 2], (
                f"pick[{i}]={picks[i]} repeated pick[{i-2}]"
            )

    def test_fallback_to_full_pool_when_all_in_history(self):
        # history_size >= pool size → should not crash, falls back to full pool
        pool = RelayPool(relays=["se-sto-wg-001", "nl-ams-wg-001"], history_size=5)
        result = pool.pick()
        assert result in pool.relays

    def test_country_code(self):
        assert RelayPool.country_code("se-sto-wg-004") == "se"
        assert RelayPool.country_code("nl-ams-wg-001") == "nl"
        assert RelayPool.country_code("") == "unknown"

    def test_city_code(self):
        assert RelayPool.city_code("se-sto-wg-004") == "sto"
        assert RelayPool.city_code("de-fra-wg-001") == "fra"

    def test_last_used_tracks_picks(self):
        pool = RelayPool(relays=["se-sto-wg-001", "nl-ams-wg-001"])
        assert pool.last_used is None
        pool.pick()
        assert pool.last_used is not None

    def test_history_property(self):
        pool = RelayPool(relays=["se-sto-wg-001", "nl-ams-wg-001", "de-ber-wg-001"])
        pool.pick()
        pool.pick()
        assert len(pool.history) == 2

    def test_refresh_updates_relays(self):
        mock_output = (
            "se-sto-wg-201\n"
            "se-sto-wg-202\n"
            "nl-ams-wg-099\n"
            "us-nyc-wg-001\n"  # should be excluded (not EU)
        )
        pool = RelayPool()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=mock_output, returncode=0)
            count = pool.refresh()
        # us-nyc excluded; only se and nl relays
        assert count == 3
        assert "us-nyc-wg-001" not in pool.relays

    def test_refresh_falls_back_on_failure(self):
        pool = RelayPool()
        original = list(pool.relays)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            count = pool.refresh()
        assert count == 0
        assert pool.relays == original


# ══════════════════════════════════════════════════════════════════════════════
# EgressResult / verify_egress
# ══════════════════════════════════════════════════════════════════════════════

def _make_egress_ok(ip: str = "89.37.63.206") -> EgressResult:
    return EgressResult(
        consensus_ip=ip,
        consensus_ok=True,
        mullvad_confirmed=True,
        responses={
            "https://am.i.mullvad.net/json": ip,
            "https://icanhazip.com": ip,
            "https://api.ipify.org?format=json": ip,
        },
        raw_mullvad={"ip": ip, "mullvad_exit_ip": True, "city": "Stockholm"},
    )


def _make_egress_leaked() -> EgressResult:
    return EgressResult(
        consensus_ip=None,
        consensus_ok=False,
        mullvad_confirmed=False,
        responses={
            "https://am.i.mullvad.net/json": "1.2.3.4",
            "https://icanhazip.com": "5.6.7.8",
            "https://api.ipify.org?format=json": "ERROR: timeout",
        },
    )


class TestEgressResult:
    def test_str_ok(self):
        r = _make_egress_ok()
        assert "OK" in str(r)
        assert "mullvad-confirmed" in str(r)

    def test_str_failed(self):
        r = _make_egress_leaked()
        assert "FAILED" in str(r)
        assert "NOT-mullvad" in str(r)

    def test_to_dict_keys(self):
        r = _make_egress_ok()
        d = r.to_dict()
        assert "consensus_ip" in d
        assert "consensus_ok" in d
        assert "mullvad_confirmed" in d


class TestVerifyEgress:
    def _patch_fetch(self, ip: str = "89.37.63.206", mullvad_confirmed: bool = True):
        """Return a side_effect that mocks _fetch_ip for all three endpoints."""
        def _side_effect(url, proxy, timeout):
            if "mullvad" in url:
                raw = {"ip": ip, "mullvad_exit_ip": mullvad_confirmed}
                return url, ip, raw
            else:
                return url, ip, {}
        return _side_effect

    def test_consensus_ok_when_all_agree(self):
        with patch("pipeline.vpn.egress._fetch_ip", side_effect=self._patch_fetch()):
            result = verify_egress(proxy=None, timeout=5.0)
        assert result.consensus_ok is True
        assert result.consensus_ip == "89.37.63.206"
        assert result.mullvad_confirmed is True

    def test_consensus_ok_on_two_of_three(self):
        call_count = {"n": 0}

        def _two_agree(url, proxy, timeout):
            call_count["n"] += 1
            if call_count["n"] == 1:  # first call returns different IP
                return url, "1.2.3.4", {}
            return url, "89.37.63.206", {}

        with patch("pipeline.vpn.egress._fetch_ip", side_effect=_two_agree):
            result = verify_egress(proxy=None, timeout=5.0,
                                   endpoints=["a", "b", "c"])
        assert result.consensus_ok is True
        assert result.consensus_ip == "89.37.63.206"

    def test_no_consensus_when_all_disagree(self):
        ips = iter(["1.1.1.1", "2.2.2.2", "3.3.3.3"])

        def _all_different(url, proxy, timeout):
            return url, next(ips), {}

        with patch("pipeline.vpn.egress._fetch_ip", side_effect=_all_different):
            result = verify_egress(proxy=None, timeout=5.0,
                                   endpoints=["a", "b", "c"])
        assert result.consensus_ok is False
        assert result.consensus_ip is None

    def test_consensus_ok_when_one_endpoint_errors(self):
        call_count = {"n": 0}

        def _one_error(url, proxy, timeout):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise ConnectionError("timeout")
            return url, "89.37.63.206", {}

        with patch("pipeline.vpn.egress._fetch_ip", side_effect=_one_error):
            result = verify_egress(proxy=None, timeout=5.0,
                                   endpoints=["a", "b", "c"])
        assert result.consensus_ok is True

    def test_fail_when_all_endpoints_error(self):
        with patch("pipeline.vpn.egress._fetch_ip", side_effect=ConnectionError("down")):
            result = verify_egress(proxy=None, timeout=5.0)
        assert result.consensus_ok is False
        assert result.consensus_ip is None


# ══════════════════════════════════════════════════════════════════════════════
# VPNManager
# ══════════════════════════════════════════════════════════════════════════════

def _mock_mullvad_connect(hostname: str, timeout: float = 30.0):
    from pipeline.vpn.mullvad import RelayInfo
    return RelayInfo(
        hostname=hostname,
        city="Stockholm",
        country="Sweden",
        ip="89.37.63.206",
    )


class TestVPNManager:
    def _make_manager(self) -> VPNManager:
        pool = RelayPool(
            relays=["se-sto-wg-001", "nl-ams-wg-001", "de-ber-wg-001"],
            history_size=1,
        )
        return VPNManager(pool=pool, allow_lan_on_connect=False, auto_obfuscate=False)

    # ── connect happy path ────────────────────────────────────────────────────

    def test_connect_sets_connected_status(self):
        mgr = self._make_manager()
        good_egress = _make_egress_ok()

        with (
            patch("pipeline.vpn.manager.connect_relay", side_effect=_mock_mullvad_connect),
            patch("pipeline.vpn.manager.wait_for_socks5", return_value=True),
            patch("pipeline.vpn.manager.detect_version", return_value=(2024, 3)),
            patch("pipeline.vpn.manager.verify_egress", return_value=good_egress),
        ):
            state = mgr.connect(relay="se-sto-wg-001")

        assert state["status"] == "connected"
        assert state["egress_verified"] is True
        assert state["mullvad_confirmed"] is True

    def test_connect_picks_from_pool_when_no_relay_given(self):
        mgr = self._make_manager()
        good_egress = _make_egress_ok()
        captured: list[str] = []

        def _capture(hostname, timeout=30):
            captured.append(hostname)
            return _mock_mullvad_connect(hostname, timeout)

        with (
            patch("pipeline.vpn.manager.connect_relay", side_effect=_capture),
            patch("pipeline.vpn.manager.wait_for_socks5", return_value=True),
            patch("pipeline.vpn.manager.detect_version", return_value=(2024, 3)),
            patch("pipeline.vpn.manager.verify_egress", return_value=good_egress),
        ):
            mgr.connect()

        assert len(captured) == 1
        assert captured[0] in mgr._pool.relays

    # ── socks5 failure ─────────────────────────────────────────────────────────

    def test_connect_raises_on_socks5_timeout(self):
        mgr = self._make_manager()

        with (
            patch("pipeline.vpn.manager.connect_relay", side_effect=_mock_mullvad_connect),
            patch("pipeline.vpn.manager.wait_for_socks5", return_value=False),
            patch("pipeline.vpn.manager.detect_version", return_value=(2024, 3)),
        ):
            with pytest.raises(Exception):
                mgr.connect(relay="se-sto-wg-001")

        assert mgr._status == VPNStatus.ERROR

    # ── egress leak ───────────────────────────────────────────────────────────

    def test_connect_raises_on_egress_leak(self):
        mgr = self._make_manager()
        leaked = _make_egress_leaked()

        with (
            patch("pipeline.vpn.manager.connect_relay", side_effect=_mock_mullvad_connect),
            patch("pipeline.vpn.manager.wait_for_socks5", return_value=True),
            patch("pipeline.vpn.manager.detect_version", return_value=(2024, 3)),
            patch("pipeline.vpn.manager.verify_egress", return_value=leaked),
        ):
            with pytest.raises(RuntimeError, match="leak"):
                mgr.connect(relay="se-sto-wg-001")

        assert mgr._status == VPNStatus.LEAKED

    # ── verify ────────────────────────────────────────────────────────────────

    def test_verify_updates_egress_state(self):
        mgr = self._make_manager()
        mgr._status = VPNStatus.CONNECTED
        good_egress = _make_egress_ok()

        with patch("pipeline.vpn.manager.verify_egress", return_value=good_egress):
            state = mgr.verify()

        assert state["egress_verified"] is True
        assert state["egress_ip"] == "89.37.63.206"

    def test_verify_raises_on_leak(self):
        mgr = self._make_manager()
        mgr._status = VPNStatus.CONNECTED
        leaked = _make_egress_leaked()

        with patch("pipeline.vpn.manager.verify_egress", return_value=leaked):
            with pytest.raises(RuntimeError):
                mgr.verify()

        assert mgr._status == VPNStatus.LEAKED

    def test_verify_noop_when_disconnected(self):
        mgr = self._make_manager()
        # status is DISCONNECTED by default — verify should be a no-op
        state = mgr.verify()
        assert state["status"] == "disconnected"

    # ── rotate ────────────────────────────────────────────────────────────────

    def test_rotate_changes_relay(self):
        mgr = self._make_manager()
        mgr._status = VPNStatus.CONNECTED
        good_egress = _make_egress_ok()
        connected_to: list[str] = []

        def _capture(hostname, timeout=30):
            connected_to.append(hostname)
            return _mock_mullvad_connect(hostname, timeout)

        with (
            patch("pipeline.vpn.manager.disconnect"),
            patch("pipeline.vpn.manager.connect_relay", side_effect=_capture),
            patch("pipeline.vpn.manager.wait_for_socks5", return_value=True),
            patch("pipeline.vpn.manager.detect_version", return_value=(2024, 3)),
            patch("pipeline.vpn.manager.verify_egress", return_value=good_egress),
        ):
            mgr.rotate()

        assert len(connected_to) == 1

    # ── disconnect ────────────────────────────────────────────────────────────

    def test_disconnect_sets_disconnected(self):
        mgr = self._make_manager()
        mgr._status = VPNStatus.CONNECTED

        with patch("pipeline.vpn.manager.disconnect"):
            state = mgr.disconnect()

        assert state["status"] == "disconnected"
        assert mgr._relay is None

    # ── alert ring ────────────────────────────────────────────────────────────

    def test_alert_ring_records_events(self):
        mgr = self._make_manager()
        good_egress = _make_egress_ok()

        with (
            patch("pipeline.vpn.manager.connect_relay", side_effect=_mock_mullvad_connect),
            patch("pipeline.vpn.manager.wait_for_socks5", return_value=True),
            patch("pipeline.vpn.manager.detect_version", return_value=(2024, 3)),
            patch("pipeline.vpn.manager.verify_egress", return_value=good_egress),
        ):
            mgr.connect(relay="se-sto-wg-001")

        events = [a["event"] for a in mgr._alerts]
        assert "connecting" in events
        assert "connected" in events

    def test_alert_ring_bounded_at_20(self):
        mgr = self._make_manager()
        for i in range(30):
            mgr._record("test_event", i=i)
        assert len(mgr._alerts) == 20

    # ── state_dict ────────────────────────────────────────────────────────────

    def test_state_dict_is_serialisable(self):
        mgr = self._make_manager()
        import json
        state = mgr.state_dict()
        # Must be JSON-serialisable (no dataclasses, no enums, no sets)
        serialised = json.dumps(state)
        assert "status" in serialised

    def test_state_dict_status_is_string(self):
        mgr = self._make_manager()
        state = mgr.state_dict()
        assert isinstance(state["status"], str)
        assert state["status"] == "disconnected"
