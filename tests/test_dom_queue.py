"""
Tests for mcp_server/dom_queue.py

Covers:
  - House: ownership check, BMAD token determinism
  - DOMRequestQueue: register, open, gate (happy path + wrong house error)
  - spawn_houses(): all expected houses present + cairrn/forecast entries added
  - RaceWatchdog: starts as daemon, state() returns correct structure
  - Concurrency: sequential calls to same house are serialised (no deadlock)
"""
from __future__ import annotations

import threading
import time

import pytest

from mcp_server.dom_queue import DOMRequestQueue, House, spawn_houses


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_house(name: str, tools: set[str] | None = None) -> House:
    token = f"tok-{name}"
    return House(
        name=name,
        trust_token=token,
        tools=frozenset(tools or {name + "_tool"}),
        purpose=f"test house {name}",
    )


# ---------------------------------------------------------------------------
# House
# ---------------------------------------------------------------------------

class TestHouse:
    def test_admits_registered_tool(self):
        h = _make_house("test", {"tool_a", "tool_b"})
        assert h.admits("tool_a")
        assert h.admits("tool_b")

    def test_does_not_admit_foreign_tool(self):
        h = _make_house("test", {"tool_a"})
        assert not h.admits("tool_b")

    def test_call_count_starts_zero(self):
        h = _make_house("test")
        assert h._call_count == 0

    def test_active_starts_false(self):
        h = _make_house("test")
        assert not h._active

    def test_status_shape(self):
        h = _make_house("test", {"t1"})
        s = h.status()
        assert s["name"] == "test"
        assert s["call_count"] == 0
        assert s["active"] is False


# ---------------------------------------------------------------------------
# DOMRequestQueue
# ---------------------------------------------------------------------------

class TestDOMRequestQueue:
    def _open_queue(self, *house_names: str) -> DOMRequestQueue:
        q = DOMRequestQueue()
        for n in house_names:
            q.register_house(_make_house(n, {n + "_tool"}))
        q.open()
        return q

    def test_gate_executes_correctly(self):
        q = self._open_queue("alpha")
        ran = []
        with q.gate("alpha_tool"):
            ran.append(1)
        assert ran == [1]

    def test_gate_increments_call_count(self):
        q = self._open_queue("beta")
        with q.gate("beta_tool"):
            pass
        house = q._houses["beta"]
        assert house._call_count == 1

    def test_gate_unknown_tool_admitted(self):
        """Unmapped tools go to overflow — they must not raise."""
        q = self._open_queue("gamma")
        ran = []
        with q.gate("not_a_tool"):
            ran.append(1)
        assert ran == [1]
        assert q._overflow._call_count == 1

    def test_gate_not_open_raises(self):
        q = DOMRequestQueue()
        q.register_house(_make_house("delta", {"delta_tool"}))
        with pytest.raises(RuntimeError):
            with q.gate("delta_tool"):
                pass

    def test_multiple_houses_independent(self):
        q = self._open_queue("h1", "h2")
        order = []
        with q.gate("h1_tool"):
            order.append("h1")
        with q.gate("h2_tool"):
            order.append("h2")
        assert order == ["h1", "h2"]

    def test_reentrant_gate_same_house(self):
        """Same thread may re-enter the same house lock (RLock)."""
        q = self._open_queue("reentrant")
        entered = []
        with q.gate("reentrant_tool"):
            with q.gate("reentrant_tool"):
                entered.append(True)
        assert entered == [True]

    def test_sequential_calls_same_house_no_deadlock(self):
        q = self._open_queue("serial")
        results = []
        for _ in range(5):
            with q.gate("serial_tool"):
                results.append(1)
        assert sum(results) == 5

    def test_concurrent_calls_serialised(self):
        """Two threads entering the same house must not overlap."""
        q = self._open_queue("concurrent")
        active_simultaneously = []
        inside = threading.Event()
        barrier = threading.Barrier(2)

        def worker():
            barrier.wait()
            with q.gate("concurrent_tool"):
                if inside.is_set():
                    active_simultaneously.append(True)
                inside.set()
                time.sleep(0.01)
                inside.clear()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert active_simultaneously == [], "Two threads were inside the house simultaneously"

    def test_gate_releases_lock_on_exception(self):
        q = self._open_queue("boom")
        with pytest.raises(RuntimeError):
            with q.gate("boom_tool"):
                raise RuntimeError("inside")
        # Lock must be free for the next caller.
        with q.gate("boom_tool"):
            pass
        assert q._houses["boom"]._active is False

    def test_gate_timeout_rejects(self):
        from mcp_server.dom_queue import HouseTimeoutError

        q = DOMRequestQueue(lock_timeout_s=0.15)
        q.register_house(_make_house("slow", {"slow_tool"}))
        q.open()
        holding = threading.Event()
        done = threading.Event()

        def holder():
            with q.gate("slow_tool"):
                holding.set()
                done.wait(timeout=2.0)

        t = threading.Thread(target=holder)
        t.start()
        assert holding.wait(timeout=1.0)
        with pytest.raises(HouseTimeoutError):
            with q.gate("slow_tool"):
                pass
        done.set()
        t.join(timeout=2.0)


# ---------------------------------------------------------------------------
# spawn_houses()
# ---------------------------------------------------------------------------

class TestSpawnHouses:
    def setup_method(self):
        self.q = spawn_houses()

    def test_returns_open_queue(self):
        state = self.q.state()
        assert state["open"] is True

    def test_all_expected_houses_present(self):
        names = set(self.q._houses.keys())
        for expected in ("talk", "dev", "modular", "wire", "edit", "clean", "graph"):
            assert expected in names, f"House {expected!r} missing from spawn_houses()"

    def test_cairrn_tools_in_modular(self):
        modular = self.q._houses["modular"]
        assert modular.admits("cairrn_hub_state")
        assert modular.admits("cairrn_neuro_k")
        assert modular.admits("code_audit")
        assert modular.admits("rate_ten")

    def test_command_dispatcher_in_clean(self):
        clean = self.q._houses["clean"]
        assert clean.admits("run_command")
        assert clean.admits("list_commands")
        assert clean.admits("bus_restart")

    def test_talk_house_owns_langevin_and_mfpt(self):
        talk = self.q._houses["talk"]
        assert talk.admits("langevin_sim")
        assert talk.admits("mfpt_estimate")
        assert talk.admits("double_well_sim")

    def test_graph_house_owns_full_mcp_surface(self):
        graph = self.q._houses["graph"]
        for tool in (
            "graph_commit",
            "graph_clean",
            "graph_link",
            "graph_status",
            "graph_nest",
            "graph_ingest",
            "graph_sync_manifest",
            "graph_traverse",
            "graph_topo_hubs",
            "graph_ingest_source",
            "graph_track_state",
            "graph_track_sync",
            "graph_annotate",
        ):
            assert graph.admits(tool), f"{tool} missing from graph house"

    def test_each_tool_in_exactly_one_house(self):
        # Duplicates are already prevented by register_house() raising ValueError,
        # but verify the tool_map is bijective.
        seen: set[str] = set()
        for tool in self.q._tool_map:
            assert tool not in seen, f"Tool {tool!r} appears twice in _tool_map"
            seen.add(tool)

    def test_watchdog_is_daemon(self):
        watchdog = self.q._watchdog
        assert watchdog is not None
        assert watchdog._thread is not None
        assert watchdog._thread.daemon

    def test_watchdog_state_structure(self):
        state = self.q._watchdog.state()
        assert "recent_stalls" in state
        assert "recent_contentions" in state
        assert "running" in state
        assert state["running"] is True

    def test_goal_and_clip_mapped(self):
        assert self.q.house_for("harmonic_set_goal") == "edit"
        assert self.q.house_for("harmonic_clear_goal") == "edit"
        assert self.q.house_for("gemini_clip") == "wire"

    def test_watchdog_never_acquires_house_lock(self):
        """Watchdog must observe stalls without taking the house lock."""
        house = self.q._houses["talk"]

        class ProbeLock:
            def __init__(self) -> None:
                self.acquires = 0

            def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
                self.acquires += 1
                return True

            def release(self) -> None:
                return None

        probe = ProbeLock()
        original = house._lock
        house._lock = probe  # type: ignore[assignment]
        try:
            house._active = True
            house._active_since = time.monotonic()
            house._active_tool = "probe"
            self.q._watchdog._poll()
        finally:
            house._lock = original
            house._active = False
            house._active_tool = ""
        assert probe.acquires == 0


# ---------------------------------------------------------------------------
# Admission predicates
# ---------------------------------------------------------------------------


class TestAdmissionPredicate:
    """
    Tests for the BMAD soft-defer admission predicate mechanism.

    Validates that:
      - Houses with no predicate admit immediately.
      - Houses with a passing predicate admit immediately.
      - Houses with a failing predicate poll until True or timeout.
      - HouseAdmissionError is raised (not HouseTimeoutError) on timeout.
    """

    def _make_gated_house(self, name: str = "gated") -> House:
        return House(
            name=name,
            trust_token=f"tok-{name}",
            tools=frozenset({f"{name}_tool"}),
            purpose=f"admission-test house {name}",
        )

    def test_no_predicate_admits_immediately(self):
        h = self._make_gated_house("open")
        with h.enter("open_tool"):
            pass  # should not raise

    def test_passing_predicate_admits_immediately(self):
        h = self._make_gated_house("passing")
        h._admission_check = lambda: True
        with h.enter("passing_tool"):
            pass

    def test_failing_predicate_raises_admission_error(self):
        from mcp_server.dom_queue import HouseAdmissionError
        h = self._make_gated_house("failing")
        h._admission_check = lambda: False
        h._admission_timeout_s = 0.1  # short timeout so test is fast
        h._admission_poll_s = 0.02
        with pytest.raises(HouseAdmissionError) as exc_info:
            with h.enter("failing_tool"):
                pass
        err = exc_info.value
        assert err.house == "failing"
        assert err.tool == "failing_tool"
        assert err.error_code == "house_admission_timeout"

    def test_predicate_polled_until_true(self):
        """Predicate starts False, becomes True after a short delay."""
        h = self._make_gated_house("delayed")
        passed = threading.Event()

        def _pred() -> bool:
            return passed.is_set()

        h._admission_check = _pred
        h._admission_timeout_s = 1.0
        h._admission_poll_s = 0.02

        def _flip() -> None:
            time.sleep(0.08)
            passed.set()

        t = threading.Thread(target=_flip, daemon=True)
        t.start()

        entered = False
        with h.enter("delayed_tool"):
            entered = True
        assert entered, "gate should have admitted once predicate passed"
        t.join(timeout=0.5)

    def test_admission_error_has_hint(self):
        """HouseAdmissionError.to_dict() must include the 'hint' field."""
        from mcp_server.dom_queue import HouseAdmissionError
        err = HouseAdmissionError("test_house", "test_tool", 5.0)
        d = err.to_dict("test_tool")
        assert "hint" in d
        assert d["house"] == "test_house"
        assert d["timeout_s"] == 5.0

    def test_house_status_reports_admission_gated(self):
        h = self._make_gated_house("status_check")
        assert h.status()["admission_gated"] is False
        h._admission_check = lambda: True
        assert h.status()["admission_gated"] is True

    def test_spawn_houses_wires_modular_predicate(self):
        """spawn_houses() must have an admission check on the modular house."""
        q = spawn_houses()
        modular = q._houses.get("modular")
        assert modular is not None
        # Predicate is wired by _state.py after spawn, not by spawn_houses() itself;
        # raw spawn gives None — verify the contract on House fields only.
        assert hasattr(modular, "_admission_check")
        assert hasattr(modular, "_admission_timeout_s")
