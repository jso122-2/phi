"""Tests for workers.base."""

import pytest

from workers.base import Worker, SimWorker, BatchWorker, Status, WorkerResult
from sims.attractors import run_double_well


# ---------------------------------------------------------------------------
# Worker basics
# ---------------------------------------------------------------------------

class TestWorker:
    def test_successful_run(self):
        w = Worker("add", lambda a, b: a + b)
        result = w.run(2, 3)
        assert result.ok
        assert result.value == 5

    def test_failed_run(self):
        def boom():
            raise ValueError("intentional")

        w = Worker("boom", boom)
        result = w.run()
        assert result.status == Status.FAILED
        assert "intentional" in result.error

    def test_history_accumulates(self):
        w = Worker("identity", lambda x: x)
        w.run(1)
        w.run(2)
        w.run(3)
        assert len(w.history) == 3

    def test_last_result(self):
        w = Worker("double", lambda x: x * 2)
        w.run(5)
        assert w.last.value == 10

    def test_elapsed_recorded(self):
        w = Worker("noop", lambda: None)
        result = w.run()
        assert result.elapsed_s >= 0.0

    def test_repr_contains_name(self):
        w = Worker("myworker", lambda: None)
        assert "myworker" in repr(w)


# ---------------------------------------------------------------------------
# SimWorker wrapping sims.attractors
# ---------------------------------------------------------------------------

class TestSimWorker:
    def test_double_well_via_worker(self):
        w = SimWorker("double-well", run_double_well)
        result = w.run(1.0)
        assert result.ok
        traj = result.value
        assert traj.converged

    def test_negative_start(self):
        w = SimWorker("double-well-neg", run_double_well)
        result = w.run(-2.0)
        assert result.ok
        assert result.value.converged_at < 0


# ---------------------------------------------------------------------------
# BatchWorker
# ---------------------------------------------------------------------------

class TestBatchWorker:
    def _make_batch(self, n: int = 3) -> BatchWorker:
        workers = [Worker(f"w{i}", lambda x, i=i: x + i) for i in range(n)]
        return BatchWorker(workers)

    def test_run_all_returns_correct_count(self):
        batch = self._make_batch(3)
        results = batch.run_all([(10,), (10,), (10,)])
        assert len(results) == 3

    def test_all_ok_when_no_errors(self):
        batch = self._make_batch(3)
        batch.run_all([(0,), (0,), (0,)])
        assert batch.all_ok

    def test_all_ok_false_when_failure(self):
        workers = [
            Worker("ok", lambda: 1),
            Worker("fail", lambda: 1 / 0),
        ]
        batch = BatchWorker(workers)
        batch.run_all([(), ()])
        assert not batch.all_ok

    def test_summary_has_worker_names(self):
        batch = self._make_batch(2)
        batch.run_all([(1,), (1,)])
        names = [s["worker"] for s in batch.summary()]
        assert names == ["w0", "w1"]
