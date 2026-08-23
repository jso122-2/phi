"""
Tests for engine/hot_loader.py — CAIRRNHotLoader speculative prefetch engine.

No disk I/O. All load_fns return synthetic values.
"""
from __future__ import annotations

import threading
import time

import pytest

from engine.hot_loader import CAIRRNHotLoader, HotLoadMetrics, HotLoadResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _immediate_loader() -> CAIRRNHotLoader:
    return CAIRRNHotLoader(max_entries=64)


def _sync_load(value: object = 42) -> object:
    return value


def _slow_load(value: object = 99, delay: float = 0.05) -> object:
    time.sleep(delay)
    return value


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegister:
    def test_register_adds_entry(self):
        hl = _immediate_loader()
        hl.register("k1", signal_fn=lambda: False, load_fn=lambda: 1)
        assert len(hl) == 1

    def test_register_overwrite_preserves_loaded_result(self):
        hl = _immediate_loader()
        hl.register("k1", signal_fn=lambda: True, load_fn=lambda: 10)
        hl.step()
        time.sleep(0.05)  # let daemon thread complete
        assert hl.get("k1") == 10
        # Overwrite — result preserved
        hl.register("k1", signal_fn=lambda: False, load_fn=lambda: 99)
        assert hl.get("k1") == 10

    def test_register_and_signal_marks_pending(self):
        hl = _immediate_loader()
        hl.register_and_signal("k1", load_fn=lambda: "hello")
        hl.step()
        time.sleep(0.05)
        assert hl.get("k1") == "hello"

    def test_unregister(self):
        hl = _immediate_loader()
        hl.register("k1", signal_fn=lambda: False, load_fn=lambda: 1)
        assert hl.unregister("k1") is True
        assert len(hl) == 0
        assert hl.unregister("nonexistent") is False

    def test_max_entries_evicts_oldest(self):
        hl = CAIRRNHotLoader(max_entries=3)
        for i in range(5):
            hl.register(f"k{i}", signal_fn=lambda: False, load_fn=lambda: i)
        assert len(hl) == 3
        # k0 and k1 should be evicted (oldest)
        assert hl.get("k0") is None
        assert hl.get("k1") is None

    def test_max_entries_zero_disables_eviction(self):
        hl = CAIRRNHotLoader(max_entries=0)
        for i in range(100):
            hl.register(f"k{i}", signal_fn=lambda: False, load_fn=lambda: i)
        assert len(hl) == 100


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------


class TestSignal:
    def test_signal_marks_pending_and_fires(self):
        hl = _immediate_loader()
        hl.register("k1", signal_fn=lambda: False, load_fn=lambda: "fired")
        assert hl.signal("k1") is True
        hl.step()
        time.sleep(0.05)
        assert hl.get("k1") == "fired"

    def test_signal_unknown_returns_false(self):
        hl = _immediate_loader()
        assert hl.signal("nonexistent") is False

    def test_signal_loaded_entry_is_noop(self):
        hl = _immediate_loader()
        hl.register("k1", signal_fn=lambda: True, load_fn=lambda: 7)
        hl.step()
        time.sleep(0.05)
        assert hl.get("k1") == 7
        # Signal again — should not reload (already loaded)
        hl.signal("k1")
        hl.step()
        time.sleep(0.05)
        assert hl.get("k1") == 7


# ---------------------------------------------------------------------------
# Step / signal_fn
# ---------------------------------------------------------------------------


class TestStep:
    def test_step_fires_when_signal_returns_true(self):
        hl = _immediate_loader()
        hl.register("k1", signal_fn=lambda: True, load_fn=lambda: "loaded")
        result = hl.step()
        assert "k1" in result.triggered
        time.sleep(0.05)
        assert hl.get("k1") == "loaded"

    def test_step_does_not_fire_when_signal_false(self):
        hl = _immediate_loader()
        hl.register("k1", signal_fn=lambda: False, load_fn=lambda: "loaded")
        result = hl.step()
        assert result.triggered == []
        assert hl.get("k1") is None

    def test_step_does_not_double_fire_loading_entry(self):
        hl = _immediate_loader()
        fired_count = [0]

        def _load():
            fired_count[0] += 1
            time.sleep(0.1)
            return fired_count[0]

        hl.register("k1", signal_fn=lambda: True, load_fn=_load)
        hl.step()
        hl.step()
        hl.step()
        time.sleep(0.2)
        # Only one thread should have fired
        assert fired_count[0] == 1

    def test_step_result_fields(self):
        hl = _immediate_loader()
        hl.register("k1", signal_fn=lambda: True, load_fn=lambda: 1)
        result = hl.step()
        assert isinstance(result, HotLoadResult)
        assert hasattr(result, "triggered")
        assert hasattr(result, "ready")
        assert hasattr(result, "loading")
        assert hasattr(result, "total")

    def test_step_ready_list_reflects_loaded_entries(self):
        hl = _immediate_loader()
        hl.register("k1", signal_fn=lambda: True, load_fn=lambda: 1)
        hl.step()
        time.sleep(0.05)
        result = hl.step()
        assert "k1" in result.ready

    def test_as_dict(self):
        hl = _immediate_loader()
        hl.register("k1", signal_fn=lambda: True, load_fn=lambda: 1)
        result = hl.step()
        d = result.as_dict()
        for key in ("triggered", "ready", "loading", "total"):
            assert key in d


# ---------------------------------------------------------------------------
# Get / is_ready
# ---------------------------------------------------------------------------


class TestGet:
    def test_get_returns_none_before_load(self):
        hl = _immediate_loader()
        hl.register("k1", signal_fn=lambda: False, load_fn=lambda: 99)
        assert hl.get("k1") is None

    def test_get_returns_value_after_load(self):
        hl = _immediate_loader()
        hl.register_and_signal("k1", load_fn=lambda: {"answer": 42})
        hl.step()
        time.sleep(0.05)
        assert hl.get("k1") == {"answer": 42}

    def test_get_nonexistent_returns_none(self):
        hl = _immediate_loader()
        assert hl.get("does_not_exist") is None

    def test_is_ready(self):
        hl = _immediate_loader()
        hl.register_and_signal("k1", load_fn=lambda: True)
        assert hl.is_ready("k1") is False
        hl.step()
        time.sleep(0.05)
        assert hl.is_ready("k1") is True


# ---------------------------------------------------------------------------
# Invalidate
# ---------------------------------------------------------------------------


class TestInvalidate:
    def test_invalidate_clears_result(self):
        hl = _immediate_loader()
        hl.register_and_signal("k1", load_fn=lambda: 7)
        hl.step()
        time.sleep(0.05)
        assert hl.get("k1") == 7
        hl.invalidate("k1")
        assert hl.get("k1") is None

    def test_invalidate_allows_reload(self):
        calls = [0]

        def _load():
            calls[0] += 1
            return calls[0]

        hl = _immediate_loader()
        hl.register_and_signal("k1", load_fn=_load)
        hl.step()
        time.sleep(0.05)
        assert hl.get("k1") == 1

        hl.invalidate("k1")
        hl.signal("k1")
        hl.step()
        time.sleep(0.05)
        assert hl.get("k1") == 2

    def test_invalidate_all(self):
        hl = _immediate_loader()
        for i in range(5):
            hl.register_and_signal(f"k{i}", load_fn=lambda v=i: v)
        hl.step()
        time.sleep(0.05)
        hl.invalidate_all()
        for i in range(5):
            assert hl.get(f"k{i}") is None


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_register_and_get(self):
        hl = _immediate_loader()
        errors: list[Exception] = []

        def _writer(n: int) -> None:
            try:
                for i in range(20):
                    hl.register_and_signal(f"k{n}_{i}", load_fn=lambda v=i: v)
                    hl.step()
            except Exception as exc:
                errors.append(exc)

        def _reader() -> None:
            try:
                for _ in range(50):
                    hl.get("k0_0")
                    hl.is_ready("k0_1")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_writer, args=(n,)) for n in range(4)]
        threads += [threading.Thread(target=_reader) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert errors == []

    def test_load_fn_exception_is_non_fatal(self):
        hl = _immediate_loader()

        def _bad_load():
            raise ValueError("boom")

        hl.register_and_signal("k1", load_fn=_bad_load)
        hl.step()
        time.sleep(0.05)
        # Entry stays unloaded but loader continues
        assert hl.get("k1") is None
        assert len(hl) == 1


# ---------------------------------------------------------------------------
# State / repr
# ---------------------------------------------------------------------------


class TestState:
    def test_state_keys(self):
        hl = _immediate_loader()
        hl.register("k1", signal_fn=lambda: False, load_fn=lambda: 1)
        st = hl.state()
        assert "total" in st
        assert "entries" in st
        assert "k1" in st["entries"]

    def test_summary_keys(self):
        hl = _immediate_loader()
        s = hl.summary()
        for k in ("total", "loaded", "loading", "unloaded"):
            assert k in s

    def test_repr_contains_total(self):
        hl = _immediate_loader()
        hl.register("k1", signal_fn=lambda: False, load_fn=lambda: 1)
        r = repr(hl)
        assert "total=1" in r


# ---------------------------------------------------------------------------
# HotLoadMetrics — unit tests
# ---------------------------------------------------------------------------


class TestHotLoadMetrics:
    def test_defaults_zero(self):
        m = HotLoadMetrics()
        assert m.hits == 0
        assert m.misses == 0
        assert m.total_lookups == 0
        assert m.hit_rate == pytest.approx(0.0)
        assert m.miss_rate == pytest.approx(0.0)
        assert m.avg_load_duration_s == pytest.approx(0.0)
        assert m.avg_latency_saved_s == pytest.approx(0.0)
        assert m.avg_lead_time_s == pytest.approx(0.0)

    def test_hit_rate_calculation(self):
        m = HotLoadMetrics(hits=7, misses=3)
        assert m.hit_rate == pytest.approx(0.7)
        assert m.miss_rate == pytest.approx(0.3)
        assert m.total_lookups == 10

    def test_avg_load_duration(self):
        m = HotLoadMetrics(loads_completed=4, sum_load_duration_s=0.8)
        assert m.avg_load_duration_s == pytest.approx(0.2)

    def test_avg_latency_saved(self):
        m = HotLoadMetrics(hits=5, sum_latency_saved_s=1.0)
        assert m.avg_latency_saved_s == pytest.approx(0.2)

    def test_avg_lead_time(self):
        m = HotLoadMetrics(leads_measured=3, sum_lead_time_s=0.6)
        assert m.avg_lead_time_s == pytest.approx(0.2)

    def test_as_dict_keys(self):
        m = HotLoadMetrics(hits=2, misses=1)
        d = m.as_dict()
        for k in ("hits", "misses", "total_lookups", "hit_rate", "miss_rate",
                  "loads_triggered", "loads_completed", "load_errors",
                  "avg_load_duration_s", "avg_latency_saved_s", "avg_lead_time_s"):
            assert k in d, f"Missing key: {k}"


# ---------------------------------------------------------------------------
# Metrics accumulation — integration tests
# ---------------------------------------------------------------------------


class TestMetricsAccumulation:
    def test_miss_on_unknown_name(self):
        hl = _immediate_loader()
        hl.get("nonexistent")
        m = hl.metrics
        assert m.misses == 1
        assert m.hits == 0

    def test_miss_on_unloaded_entry(self):
        hl = _immediate_loader()
        hl.register("k1", signal_fn=lambda: False, load_fn=lambda: 42)
        hl.get("k1")  # not yet loaded
        m = hl.metrics
        assert m.misses == 1
        assert m.hits == 0

    def test_hit_after_load(self):
        hl = _immediate_loader()
        hl.register_and_signal("k1", load_fn=lambda: 99)
        hl.step()
        time.sleep(0.05)
        val = hl.get("k1")
        assert val == 99
        m = hl.metrics
        assert m.hits == 1
        assert m.misses == 0

    def test_hit_rate_after_mixed_lookups(self):
        hl = _immediate_loader()
        hl.register_and_signal("k1", load_fn=lambda: 1)
        hl.step()
        time.sleep(0.05)
        hl.get("k1")   # hit
        hl.get("k1")   # hit again (still loaded)
        hl.get("k99")  # miss — not registered
        m = hl.metrics
        assert m.hits == 2
        assert m.misses == 1
        assert m.hit_rate == pytest.approx(2 / 3)

    def test_loads_triggered_counted(self):
        hl = _immediate_loader()
        hl.register_and_signal("k1", load_fn=lambda: 1)
        hl.register_and_signal("k2", load_fn=lambda: 2)
        hl.step()
        m = hl.metrics
        assert m.loads_triggered == 2

    def test_loads_completed_counted(self):
        hl = _immediate_loader()
        hl.register_and_signal("k1", load_fn=lambda: 1)
        hl.step()
        time.sleep(0.05)
        m = hl.metrics
        assert m.loads_completed == 1
        assert m.load_errors == 0

    def test_load_errors_counted(self):
        hl = _immediate_loader()
        hl.register_and_signal("k1", load_fn=lambda: 1 / 0)
        hl.step()
        time.sleep(0.05)
        m = hl.metrics
        assert m.load_errors == 1
        assert m.loads_completed == 0

    def test_avg_load_duration_positive(self):
        hl = _immediate_loader()

        def _slow():
            time.sleep(0.02)
            return 7

        hl.register_and_signal("k1", load_fn=_slow)
        hl.step()
        time.sleep(0.08)
        m = hl.metrics
        assert m.loads_completed == 1
        assert m.avg_load_duration_s >= 0.01

    def test_avg_latency_saved_positive_on_hit(self):
        hl = _immediate_loader()

        def _slow():
            time.sleep(0.02)
            return 42

        hl.register_and_signal("k1", load_fn=_slow)
        hl.step()
        time.sleep(0.08)
        hl.get("k1")
        m = hl.metrics
        assert m.hits == 1
        assert m.avg_latency_saved_s >= 0.01

    def test_lead_time_positive_when_ahead_of_demand(self):
        hl = _immediate_loader()
        hl.register_and_signal("k1", load_fn=lambda: "fast")
        hl.step()
        time.sleep(0.05)   # load completes first
        hl.get("k1")       # caller arrives after
        m = hl.metrics
        assert m.leads_measured == 1
        assert m.avg_lead_time_s > 0.0

    def test_lead_time_recorded_only_on_first_hit(self):
        hl = _immediate_loader()
        hl.register_and_signal("k1", load_fn=lambda: "x")
        hl.step()
        time.sleep(0.05)
        hl.get("k1")
        hl.get("k1")
        hl.get("k1")
        m = hl.metrics
        assert m.hits == 3
        assert m.leads_measured == 1

    def test_reset_metrics_clears_counters(self):
        hl = _immediate_loader()
        hl.register_and_signal("k1", load_fn=lambda: 1)
        hl.step()
        time.sleep(0.05)
        hl.get("k1")
        assert hl.metrics.hits > 0
        hl.reset_metrics()
        m = hl.metrics
        assert m.hits == 0
        assert m.misses == 0
        assert m.loads_triggered == 0
        assert m.loads_completed == 0

    def test_is_ready_does_not_record_metrics(self):
        hl = _immediate_loader()
        hl.register_and_signal("k1", load_fn=lambda: 1)
        hl.step()
        time.sleep(0.05)
        assert hl.is_ready("k1") is True
        m = hl.metrics
        assert m.hits == 0
        assert m.misses == 0

    def test_metrics_in_state_dict(self):
        hl = _immediate_loader()
        st = hl.state()
        assert "metrics" in st

    def test_metrics_in_summary_dict(self):
        hl = _immediate_loader()
        s = hl.summary()
        assert "metrics" in s

    def test_repr_shows_hit_rate_and_lead(self):
        hl = _immediate_loader()
        r = repr(hl)
        assert "hit_rate=" in r
        assert "lead=" in r
