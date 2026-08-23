"""Tests for the Phase-1 session orientation document (write_live_init)
and the Phase-2 coherence queue builder (_build_coherence_queue)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# write_live_init
# ---------------------------------------------------------------------------

class TestWriteLiveInit:
    def _call(self, tmp_path: Path, **kwargs):
        import graph.node as gn
        # Redirect SESSIONS_DIR to tmp_path so tests don't pollute the vault
        orig = gn.SESSIONS_DIR
        gn.SESSIONS_DIR = tmp_path
        try:
            from graph.node import write_live_init
            return write_live_init(**kwargs)
        finally:
            gn.SESSIONS_DIR = orig

    def test_writes_file(self, tmp_path):
        p = self._call(
            tmp_path,
            hub_activations={"CODE": 0.5, "HOME": 0.1},
            total_activation=0.6,
            step_count=10,
            startup_errors={},
        )
        assert p.exists()
        assert p.name == "live-init.md"

    def test_hub_activations_ordered(self, tmp_path):
        p = self._call(
            tmp_path,
            hub_activations={"HOME": 0.1, "CODE": 0.8, "MATH": 0.3},
            total_activation=1.2,
            step_count=5,
            startup_errors={},
        )
        text = p.read_text()
        # CODE should appear before MATH which should appear before HOME
        assert text.index("CODE") < text.index("MATH") < text.index("HOME")

    def test_startup_errors_shown(self, tmp_path):
        p = self._call(
            tmp_path,
            hub_activations={},
            total_activation=0.0,
            step_count=0,
            startup_errors={"harmonic": "import failed"},
        )
        text = p.read_text()
        assert "harmonic" in text
        assert "degraded" in text

    def test_healthy_boot_status(self, tmp_path):
        p = self._call(
            tmp_path,
            hub_activations={"CODE": 0.4},
            total_activation=0.4,
            step_count=3,
            startup_errors={},
        )
        assert "healthy" in p.read_text()

    def test_last_session_included(self, tmp_path):
        p = self._call(
            tmp_path,
            hub_activations={},
            total_activation=0.0,
            step_count=0,
            startup_errors={},
            last_session={
                "stem": "2026-08-22-modular",
                "title": "Modularise god files",
                "outcome_snippet": "1829 tests pass",
            },
        )
        text = p.read_text()
        assert "Modularise god files" in text
        assert "1829 tests pass" in text

    def test_no_last_session(self, tmp_path):
        p = self._call(
            tmp_path,
            hub_activations={},
            total_activation=0.0,
            step_count=0,
            startup_errors={},
            last_session=None,
        )
        assert "no prior session" in p.read_text()

    def test_phase2_pending_notice(self, tmp_path):
        p = self._call(
            tmp_path,
            hub_activations={},
            total_activation=0.0,
            step_count=0,
            startup_errors={},
        )
        assert "live-context" in p.read_text().lower()
        assert "[coherence] ready" in p.read_text() or "coherence" in p.read_text()

    def test_dominant_hub_named(self, tmp_path):
        p = self._call(
            tmp_path,
            hub_activations={"HOME": 0.05, "CODE": 0.9, "MATH": 0.2},
            total_activation=1.15,
            step_count=1,
            startup_errors={},
        )
        assert "**CODE**" in p.read_text()


# ---------------------------------------------------------------------------
# _last_session_summary
# ---------------------------------------------------------------------------

class TestLastSessionSummary:
    def test_returns_none_when_no_sessions(self, tmp_path, monkeypatch):
        import graph.node as gn
        monkeypatch.setattr(gn, "SESSIONS_DIR", tmp_path)
        from graph.node import _last_session_summary
        assert _last_session_summary() is None

    def test_skips_live_files(self, tmp_path, monkeypatch):
        import graph.node as gn
        monkeypatch.setattr(gn, "SESSIONS_DIR", tmp_path)
        (tmp_path / "live-init.md").write_text("# Session Init\n")
        (tmp_path / "live-context.md").write_text("# Live Context\n")
        from graph.node import _last_session_summary
        assert _last_session_summary() is None

    def test_picks_most_recent(self, tmp_path, monkeypatch):
        import graph.node as gn
        monkeypatch.setattr(gn, "SESSIONS_DIR", tmp_path)
        import time
        (tmp_path / "2026-01-01-older.md").write_text(
            "# Session: old\n\n**Outcome:**\nold outcome\n---\n"
        )
        time.sleep(0.05)
        (tmp_path / "2026-08-22-newer.md").write_text(
            "# Session: new\n\n**Outcome:**\nnew outcome\n---\n"
        )
        from graph.node import _last_session_summary
        result = _last_session_summary()
        assert result is not None
        assert result["stem"] == "2026-08-22-newer"
        assert "new outcome" in result["outcome_snippet"]


# ---------------------------------------------------------------------------
# _build_coherence_queue
# ---------------------------------------------------------------------------

class TestBuildCoherenceQueue:
    def _call(self, acts: list[float]):
        from mcp_server._context_hook import _build_coherence_queue
        return _build_coherence_queue(np.array(acts, dtype=float))

    def test_empty_when_cold(self):
        queue = self._call([0.0] * 8)
        assert queue == []

    def test_ordered_by_activation_desc(self):
        # CODE = shards 3,4 → inject high values
        acts = [0.0] * 8
        acts[3] = 0.8
        acts[4] = 0.6   # CODE total = 1.4
        acts[1] = 0.3   # MATH shard 1
        queue = self._call(acts)
        assert len(queue) >= 2
        assert queue[0]["hub"] == "CODE"
        assert queue[0]["activation"] > queue[1]["activation"]

    def test_noise_floor_filters_cold_hubs(self):
        acts = [0.0] * 8
        acts[0] = 1e-5   # HOME — below noise floor
        acts[3] = 0.5    # CODE — above
        queue = self._call(acts)
        hubs = [e["hub"] for e in queue]
        assert "CODE" in hubs
        assert "HOME" not in hubs

    def test_suggestions_present(self):
        acts = [0.0] * 8
        acts[3] = 0.5   # CODE
        queue = self._call(acts)
        assert len(queue) == 1
        assert len(queue[0]["suggestions"]) > 0

    def test_shards_listed(self):
        acts = [0.0] * 8
        acts[1] = 0.4   # MATH shard 1
        acts[2] = 0.3   # MATH shard 2
        queue = self._call(acts)
        math_entry = next(e for e in queue if e["hub"] == "MATH")
        assert set(math_entry["shards"]) == {1, 2}
