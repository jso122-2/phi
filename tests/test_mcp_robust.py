"""
Robustness tests for the MCP server crash envelope.

These do not spawn a stdio subprocess.  They pin the contracts that keep
the server alive: JSON-safe payloads, exception → error dict, vault writes
that never raise, and hooks that cannot kill the process.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from mcp_server._guard import (
    MCPToolError,
    install_tool_guard,
    invoke_guarded,
    json_safe,
    tool_error,
)
from mcp_server.hooks import HookRegistry, HookViolation
from mcp_server.vault_hub import VaultHub


class TestJsonSafe:
    def test_primitives(self):
        assert json_safe(None) is None
        assert json_safe(True) is True
        assert json_safe(3) == 3
        assert json_safe("ok") == "ok"

    def test_nan_and_inf_become_none(self):
        assert json_safe(float("nan")) is None
        assert json_safe(float("inf")) is None
        assert json_safe(float("-inf")) is None

    def test_nested_and_path(self):
        payload = json_safe({
            "path": Path("/tmp/x"),
            "tags": {"a", "b"},
            "vals": (1, 2.0),
        })
        json.dumps(payload)
        assert payload["path"] == "/tmp/x"
        assert sorted(payload["tags"]) == ["a", "b"]

    def test_numpy_scalar_if_present(self):
        np = pytest.importorskip("numpy")
        assert json_safe(np.int64(7)) == 7
        assert json_safe(np.float64(1.5)) == 1.5
        assert json_safe(np.array([1, 2, 3])) == [1, 2, 3]

    def test_unknown_object_repr(self):
        class Blob:
            def __repr__(self) -> str:
                return "Blob()"
        assert json_safe(Blob()) == "Blob()"

    def test_depth_cap(self):
        nested: dict = {}
        cur = nested
        for _ in range(40):
            nxt: dict = {}
            cur["k"] = nxt
            cur = nxt
        out = json_safe(nested)
        dumped = json.dumps(out)
        assert "<max_depth>" in dumped


class TestInvokeGuarded:
    def test_success_passthrough(self):
        def ok(x: int) -> dict:
            return {"n": x}
        assert invoke_guarded(ok, 3) == {"n": 3}

    def test_unexpected_exception_becomes_dict(self):
        def boom() -> dict:
            raise ValueError("nope")
        result = invoke_guarded(boom)
        assert result["error"] == "tool_exception"
        assert result["type"] == "ValueError"
        assert result["message"] == "nope"
        json.dumps(result)

    def test_mcp_tool_error_no_traceback_payload(self):
        class Slow(MCPToolError):
            error_code = "house_timeout"

        def blocked() -> dict:
            raise Slow("held")

        result = invoke_guarded(blocked)
        assert result["error"] == "house_timeout"
        assert "type" not in result
        json.dumps(result)

    def test_nan_in_result_stripped(self):
        def bad() -> dict:
            return {"v": math.nan}
        result = invoke_guarded(bad)
        assert result["v"] is None

    def test_tool_error_shape(self):
        payload = tool_error("x", RuntimeError("z"))
        assert payload == {
            "error": "tool_exception",
            "tool": "x",
            "type": "RuntimeError",
            "message": "z",
        }


class TestInstallToolGuard:
    def test_idempotent(self):
        class Dummy:
            def tool(self, *a, **k):
                def deco(fn):
                    return fn
                return deco

        mcp = Dummy()
        install_tool_guard(mcp)
        first = mcp.tool
        install_tool_guard(mcp)
        assert mcp.tool is first

    def test_registered_fn_never_raises(self):
        registered = {}

        class Dummy:
            def tool(self, *a, **k):
                def deco(fn):
                    registered["fn"] = fn
                    return fn
                return deco

        mcp = Dummy()
        install_tool_guard(mcp)

        @mcp.tool()
        def explode() -> dict:
            raise KeyError("missing")

        result = registered["fn"]()
        assert result["error"] == "tool_exception"
        assert result["type"] == "KeyError"


class TestVaultHubWrite:
    def test_write_failure_does_not_raise(self, tmp_path, monkeypatch):
        hub = VaultHub(tmp_path)
        hub._harmonic = {"step": 1, "shards": []}

        def boom(*_a, **_k):
            raise OSError("disk full")

        monkeypatch.setattr(Path, "write_text", boom)
        hub.push_harmonic({"step": 2, "shards": []})  # must not raise

    def test_atomic_replace_lands_on_target(self, tmp_path):
        hub = VaultHub(tmp_path)
        hub.push_harmonic({
            "step": 1,
            "alpha": 1.96,
            "total_activation": 0.0,
            "shards": [],
        })
        target = tmp_path / "live-state.md"
        assert target.exists()
        assert not (tmp_path / "live-state.md.tmp").exists()
        text = target.read_text(encoding="utf-8")
        assert "live-state" in text


class TestHookIsolation:
    def test_unexpected_hook_exception_becomes_violation(self):
        reg = HookRegistry()

        def bad(_tool: str, _kwargs: dict) -> None:
            raise RuntimeError("hook exploded")

        reg.register("bad", "boom", bad)
        with pytest.raises(HookViolation) as exc:
            reg.run("any_tool", {})
        assert "hook exploded" in str(exc.value)

    def test_hook_violation_still_short_circuits(self):
        reg = HookRegistry()
        ran = []

        def first(_t: str, _k: dict) -> None:
            raise HookViolation("stop")

        def second(_t: str, _k: dict) -> None:
            ran.append(1)

        reg.register("a", "a", first)
        reg.register("b", "b", second)
        with pytest.raises(HookViolation):
            reg.run("t", {})
        assert ran == []


class TestDeadmanWire:
    def test_cerberus_exported_from_workers_package(self):
        from workers import CerberusGuard, CerberusExhausted
        assert callable(CerberusGuard)
        assert issubclass(CerberusExhausted, RuntimeError)

    def test_stdio_loop_is_not_cerberus_wrapped(self):
        import inspect

        import mcp_server.server as server
        src = inspect.getsource(server)
        assert "CerberusGuard" not in src
        assert "BusHost" in src

    def test_retrigger_warmups_steps_hot_loader(self):
        import time

        import mcp_server._state as st

        assert st._hot_loader is not None
        fired: list[str] = []
        st._hot_loader.register(
            "warmup:phi",
            signal_fn=lambda: False,
            load_fn=lambda: fired.append("phi") or True,
        )
        before = st._retrigger_count
        st.retrigger_warmups()
        deadline = time.monotonic() + 1.0
        while not fired and time.monotonic() < deadline:
            time.sleep(0.01)
        assert st._retrigger_count == before + 1
        assert fired == ["phi"]

    def test_stall_callback_fires_on_record(self):
        from mcp_server.dom_queue import DOMRequestQueue, House, RaceWatchdog

        q = DOMRequestQueue()
        q.register_house(House(
            name="alpha",
            trust_token="t",
            tools=frozenset({"alpha_tool"}),
            purpose="test",
        ))
        q.open()
        seen: list[dict] = []
        q._on_stall = lambda event: seen.append(event)  # type: ignore[attr-defined]
        wd = RaceWatchdog(q, stall_threshold_ms=1.0, poll_interval_ms=50.0)
        wd._record_stall(q._houses["alpha"], 1.0)
        assert len(seen) == 1
        assert seen[0]["house"] == "alpha"


class TestRunTestsCwd:
    def test_pytest_cwd_is_package_root(self):
        from mcp_server.tools.system import _PACKAGE_ROOT, _pytest_cwd
        root = Path(_pytest_cwd())
        assert root == _PACKAGE_ROOT
        assert (root / "tests" / "test_mcp_wire.py").is_file()
        assert (root / "mcp_server" / "server.py").is_file()


class TestCatalogCap:
    def test_registered_tools_fit_cursor_cap(self):
        import mcp_server.tools as tools_pkg
        from mcp_server._state import mcp

        names = sorted(mcp._tool_manager._tools)
        assert len(names) <= tools_pkg.CURSOR_MCP_TOOL_CAP, (
            f"{len(names)} tools exceed Cursor cap {tools_pkg.CURSOR_MCP_TOOL_CAP}"
        )
        for required in (
            "run_command", "list_commands", "graph_annotate", "code_audit",
            "cairrn_css_state", "cairrn_m3_gate", "cairrn_neuro_k", "bus_restart",
        ):
            assert required in names, f"{required} missing from FastMCP catalog"


class TestPhiEngineIsolation:
    def test_zone_clusterer_is_lazy(self):
        init = (Path(__file__).resolve().parent.parent / "phi" / "engine" / "__init__.py").read_text()
        assert "from phi.engine.zone_clusterer" not in init
        assert "from phi.engine.curve_daemon" not in init
        assert '"ZoneClusterer"' in init or "'ZoneClusterer'" in init

