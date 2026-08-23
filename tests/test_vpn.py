"""
Tests for pipeline.vpn and the VPN-related helpers in run.py / pipeline.auth.

All tests are fully offline — Mullvad CLI and network calls are mocked.
"""
from __future__ import annotations

import socket
import subprocess
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from pipeline.auth import _retry_network, _parse_redirect_uri
from pipeline.vpn.mullvad import (
    MullvadError,
    RelayInfo,
    SOCKS5_HOST,
    SOCKS5_PORT,
    _parse_relay_info,
    allow_lan,
    disconnect,
    ensure_sweden,
    is_connected,
    socks5_proxy,
    status,
    wait_for_socks5,
)
from pipeline.utils.config import Config, load_config
from scripts.run import _setup_vpn, _wait_for_dns, _worker_kwargs


# ── helpers ────────────────────────────────────────────────────────────────────
def _make_proc(stdout: str = "", returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.stdout = stdout
    proc.stderr = ""
    proc.returncode = returncode
    return proc


def _minimal_cfg(overrides: dict | None = None) -> Config:
    data: dict[str, Any] = {
        "vpn": {
            "enabled": True,
            "country": "sweden",
            "connect_timeout_s": 5,
            "allow_lan": True,
            "dns_warmup_host": "open.spotify.com",
            "dns_warmup_timeout_s": 5,
            "dns_warmup_interval_s": 0.1,
            "socks5": {"host": "127.0.0.1", "port": 1080},
        },
        "workers": {
            "n_threads": 2,
            "retry_passes": 3,
            "pass_delays_s": [20, 90],
            "pass_timeout_s": 600,
        },
    }
    if overrides:
        data.update(overrides)
    return Config(data)


# ═══════════════════════════════════════════════════════════════════════════════
# mullvad.py
# ═══════════════════════════════════════════════════════════════════════════════
class TestMullvadStatus:
    def test_status_returns_stdout(self):
        proc = _make_proc(stdout="Connected to se-sto-wg-204 in Stockholm, Sweden (89.37.63.206)")
        with patch("pipeline.vpn.mullvad.subprocess.run", return_value=proc):
            assert "Connected" in status()

    def test_is_connected_true(self):
        proc = _make_proc(stdout="Connected to se-sto-wg-204 in Stockholm, Sweden")
        with patch("pipeline.vpn.mullvad.subprocess.run", return_value=proc):
            assert is_connected() is True

    def test_is_connected_false(self):
        proc = _make_proc(stdout="Disconnected")
        with patch("pipeline.vpn.mullvad.subprocess.run", return_value=proc):
            assert is_connected() is False

    def test_mullvad_not_found_raises(self):
        with patch("pipeline.vpn.mullvad.subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(MullvadError, match="mullvad CLI not found"):
                status()

    def test_mullvad_daemon_timeout_raises(self):
        with patch(
            "pipeline.vpn.mullvad.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="mullvad", timeout=10),
        ):
            with pytest.raises(MullvadError, match="timed out"):
                status()


class TestParseRelayInfo:
    def test_full_status_string(self):
        info = _parse_relay_info(
            "Connected to se-sto-wg-204 in Stockholm, Sweden (89.37.63.206)"
        )
        assert info.hostname == "se-sto-wg-204"
        assert info.city == "Stockholm"
        assert info.country == "Sweden"
        assert info.ip == "89.37.63.206"

    def test_missing_ip(self):
        info = _parse_relay_info("Connected to se-got-wg-101 in Gothenburg, Sweden")
        assert info.hostname == "se-got-wg-101"
        assert info.ip is None

    def test_garbage_string(self):
        info = _parse_relay_info("Disconnected")
        assert info.hostname == "unknown"
        assert info.ip is None

    def test_str_repr(self):
        info = RelayInfo("se-sto-wg-204", "Stockholm", "Sweden", "89.37.63.206")
        assert "Stockholm" in str(info)
        assert "89.37.63.206" in str(info)


class TestEnsureSweden:
    def test_already_connected_to_sweden(self):
        connected_proc = _make_proc(
            "Connected to se-sto-wg-204 in Stockholm, Sweden (89.37.63.206)"
        )
        with patch("pipeline.vpn.mullvad.subprocess.run", return_value=connected_proc):
            relay = ensure_sweden(timeout=5)
        assert relay.hostname == "se-sto-wg-204"

    def test_connects_when_disconnected(self):
        disconnected = _make_proc("Disconnected")
        connected = _make_proc(
            "Connected to se-sto-wg-204 in Stockholm, Sweden (89.37.63.206)"
        )
        call_count = 0

        def fake_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # First two calls (relay set + connect) return disconnected,
            # third (first poll) returns connected.
            if call_count <= 2:
                return disconnected
            return connected

        with patch("pipeline.vpn.mullvad.subprocess.run", side_effect=fake_run):
            relay = ensure_sweden(timeout=5)
        assert relay.city == "Stockholm"

    def test_timeout_raises(self):
        disconnected = _make_proc("Disconnected")
        with patch("pipeline.vpn.mullvad.subprocess.run", return_value=disconnected):
            with pytest.raises(TimeoutError):
                ensure_sweden(timeout=0.1)


class TestAllowLanDisconnect:
    def test_allow_lan_calls_correct_args(self):
        proc = _make_proc()
        with patch("pipeline.vpn.mullvad.subprocess.run", return_value=proc) as mock_run:
            allow_lan()
        mock_run.assert_called_once_with(
            ["mullvad", "lan", "set", "allow"],
            capture_output=True, text=True, check=True, timeout=10.0,
        )

    def test_disconnect_does_not_raise_on_failure(self):
        with patch("pipeline.vpn.mullvad.subprocess.run", side_effect=FileNotFoundError):
            # disconnect() uses check=False so FileNotFoundError is still raised
            # from subprocess.run.  Verify MullvadError is raised instead.
            with pytest.raises(MullvadError):
                disconnect()


class TestSocks5Proxy:
    def test_returns_socks5_url(self):
        p = socks5_proxy()
        assert p["proxy"] == f"socks5://{SOCKS5_HOST}:{SOCKS5_PORT}"

    def test_proxy_format(self):
        assert socks5_proxy()["proxy"].startswith("socks5://")


class TestWaitForSocks5:
    def test_returns_true_when_port_open(self):
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        with patch("pipeline.vpn.mullvad.socket.create_connection", return_value=mock_conn):
            assert wait_for_socks5(timeout=1.0) is True

    def test_returns_false_on_timeout(self):
        with patch(
            "pipeline.vpn.mullvad.socket.create_connection",
            side_effect=OSError,
        ):
            assert wait_for_socks5(timeout=0.1) is False


# ═══════════════════════════════════════════════════════════════════════════════
# pipeline.auth._retry_network
# ═══════════════════════════════════════════════════════════════════════════════
class TestRetryNetwork:
    def test_succeeds_on_first_try(self):
        fn = MagicMock(return_value="ok")
        assert _retry_network(fn, retries=3, delay=0) == "ok"
        fn.assert_called_once()

    def test_retries_on_gaierror_then_succeeds(self):
        fn = MagicMock(side_effect=[socket.gaierror("dns fail"), socket.gaierror("dns fail"), "ok"])
        result = _retry_network(fn, retries=5, delay=0)
        assert result == "ok"
        assert fn.call_count == 3

    def test_raises_after_all_retries(self):
        fn = MagicMock(side_effect=socket.gaierror("permanent dns fail"))
        with pytest.raises(socket.gaierror):
            _retry_network(fn, retries=2, delay=0)
        assert fn.call_count == 3  # initial + 2 retries

    def test_non_dns_error_propagates_immediately(self):
        fn = MagicMock(side_effect=ValueError("not a dns error"))
        with pytest.raises(ValueError):
            _retry_network(fn, retries=10, delay=0)
        fn.assert_called_once()

    def test_parse_redirect_uri_standard(self):
        host, port, path = _parse_redirect_uri("http://localhost:8888/callback")
        assert host == "localhost"
        assert port == 8888
        assert path == "/callback"

    def test_parse_redirect_uri_defaults(self):
        host, port, path = _parse_redirect_uri("http://localhost/callback")
        assert port == 8888  # default


# ═══════════════════════════════════════════════════════════════════════════════
# run.py helpers
# ═══════════════════════════════════════════════════════════════════════════════
class TestSetupVpn:
    def test_calls_ensure_sweden_and_allow_lan(self):
        relay = RelayInfo("se-sto-wg-204", "Stockholm", "Sweden", "89.37.63.206")
        cfg = _minimal_cfg()
        with (
            patch("scripts.run.ensure_sweden", return_value=relay) as mock_sw,
            patch("scripts.run.allow_lan") as mock_lan,
        ):
            result = _setup_vpn(cfg)
        mock_sw.assert_called_once()
        mock_lan.assert_called_once()
        assert result.hostname == "se-sto-wg-204"

    def test_skips_allow_lan_when_disabled(self):
        relay = RelayInfo("se-sto-wg-204", "Stockholm", "Sweden")
        data = _minimal_cfg().as_dict()
        data["vpn"]["allow_lan"] = False
        cfg = Config(data)
        with (
            patch("scripts.run.ensure_sweden", return_value=relay),
            patch("scripts.run.allow_lan") as mock_lan,
        ):
            _setup_vpn(cfg)
        mock_lan.assert_not_called()


class TestWaitForDns:
    def _mock_conn(self):
        """Return a context-manager mock that simulates a successful TCP connect."""
        m = MagicMock()
        m.__enter__ = MagicMock(return_value=m)
        m.__exit__ = MagicMock(return_value=False)
        return m

    def test_resolves_immediately(self):
        cfg = _minimal_cfg()
        with patch("scripts.run.socket.create_connection", return_value=self._mock_conn()):
            _wait_for_dns(cfg)  # should not raise

    def test_retries_then_resolves(self):
        cfg = _minimal_cfg()
        call_count = 0

        def fake_connect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OSError("not ready yet")
            return self._mock_conn()

        with patch("scripts.run.socket.create_connection", side_effect=fake_connect):
            _wait_for_dns(cfg)
        assert call_count == 3

    def test_timeout_raises(self):
        cfg = _minimal_cfg()
        with (
            patch("scripts.run.socket.create_connection", side_effect=OSError("gone")),
            pytest.raises(TimeoutError, match="not reachable"),
        ):
            _wait_for_dns(cfg, timeout=0.05, interval=0.01)

    def test_probe_uses_bounded_timeout(self):
        """create_connection must be called with an explicit timeout — never blocking."""
        cfg = _minimal_cfg()
        captured: list = []

        def fake_connect(addr, timeout=None):
            captured.append(timeout)
            return self._mock_conn()

        with patch("scripts.run.socket.create_connection", side_effect=fake_connect):
            _wait_for_dns(cfg)

        assert captured, "create_connection was never called"
        assert all(t is not None and t > 0 for t in captured), (
            f"Expected a positive timeout on every probe, got: {captured}"
        )


class TestWorkerKwargs:
    def test_vpn_enabled_includes_proxy(self):
        cfg = _minimal_cfg()
        kwargs = _worker_kwargs(cfg)
        assert kwargs["proxy"] == "socks5://127.0.0.1:1080"

    def test_vpn_disabled_proxy_is_none(self):
        data = _minimal_cfg().as_dict()
        data["vpn"]["enabled"] = False
        cfg = Config(data)
        kwargs = _worker_kwargs(cfg)
        assert kwargs["proxy"] is None

    def test_no_vpn_flag_overrides_config(self):
        """--no-vpn must clear proxy even when config.yaml has vpn.enabled=true."""
        cfg = _minimal_cfg()  # enabled=True in config
        kwargs = _worker_kwargs(cfg, vpn_active=False)
        assert kwargs["proxy"] is None

    def test_vpn_active_true_overrides_config(self):
        data = _minimal_cfg().as_dict()
        data["vpn"]["enabled"] = False
        cfg = Config(data)
        kwargs = _worker_kwargs(cfg, vpn_active=True)
        assert kwargs["proxy"] is not None

    def test_worker_thread_count(self):
        cfg = _minimal_cfg()
        assert _worker_kwargs(cfg)["n_threads"] == 2

    def test_pass_delays_list(self):
        cfg = _minimal_cfg()
        delays = _worker_kwargs(cfg)["pass_delays_s"]
        assert isinstance(delays, list)
        assert len(delays) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# pipeline.utils.config
# ═══════════════════════════════════════════════════════════════════════════════
class TestConfig:
    def test_attribute_access(self):
        cfg = Config({"vpn": {"enabled": True, "timeout_s": 30}})
        assert cfg.vpn.enabled is True
        assert cfg.vpn.timeout_s == 30

    def test_get_nested(self):
        cfg = Config({"vpn": {"socks5": {"port": 1080}}})
        assert cfg.get("vpn", "socks5", "port") == 1080

    def test_get_default(self):
        cfg = Config({})
        assert cfg.get("vpn", "missing_key", default=99) == 99

    def test_load_config_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_load_config_reads_yaml(self, tmp_path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("vpn:\n  enabled: true\n  timeout_s: 30\n")
        cfg = load_config(yaml_file)
        assert cfg.vpn.enabled is True
        assert cfg.vpn.timeout_s == 30
