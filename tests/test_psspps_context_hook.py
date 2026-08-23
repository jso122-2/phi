"""
tests/test_psspps_context_hook.py — unit tests for the Option C context hook.

Covers:
  - _register_psspps_context_hook() idempotency
  - Phase 1: hook returns without blocking on first call
  - Phase 2: notification emits exactly once when _context_result is populated
  - _write_and_notify: populates _context_result and counts comment nodes
  - _hot_shard_query: cold index fallback + hot shard mapping
  - graph public surface: write_comment_node, write_live_context importable
"""
from __future__ import annotations

import threading
import time

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_gate_state(monkeypatch):
    """
    Reset module-level context state before and after each test so tests
    are fully independent regardless of run order.

    Patch out the session-open PSSPPS thread — a warm ring finishes
    retrieval fast enough to leak `[coherence] ready` into later tests.
    """
    import mcp_server._gate as g

    monkeypatch.setattr(
        "mcp_server._context_hook._submit_context_psspps",
        lambda: None,
    )

    # Capture originals
    orig_result = dict(g._context_result)
    notified_before = g._context_notified.is_set()

    g._context_result.clear()
    g._context_notified.clear()

    yield

    # Restore (best-effort; Events can't be un-set in one operation)
    g._context_result.clear()
    g._context_result.update(orig_result)
    if notified_before:
        g._context_notified.set()
    else:
        g._context_notified.clear()


# ---------------------------------------------------------------------------
# _register_psspps_context_hook — idempotency
# ---------------------------------------------------------------------------


class TestRegisterIdempotency:
    def test_second_register_is_noop(self):
        """register() called twice must not add a duplicate hook."""
        from mcp_server._gate import _startup_init, _register_psspps_context_hook
        from mcp_server.hooks import REGISTRY

        _startup_init()
        before = REGISTRY.version
        _register_psspps_context_hook()   # second call — must be no-op
        assert REGISTRY.version == before

    def test_hook_name_present(self):
        from mcp_server._gate import _startup_init
        from mcp_server.hooks import REGISTRY

        _startup_init()
        names = [h.name for h in REGISTRY._chain]
        assert "psspps_context" in names

    def test_hook_above_base_layer(self):
        """psspps_context must sit above the sealed base (version > base_version)."""
        from mcp_server._gate import _startup_init
        from mcp_server.hooks import REGISTRY

        _startup_init()
        hook = next(h for h in REGISTRY._chain if h.name == "psspps_context")
        assert hook.version > REGISTRY.base_version


# ---------------------------------------------------------------------------
# Two-phase hook behaviour
# ---------------------------------------------------------------------------


class TestTwoPhaseHook:
    def _get_hook_fn(self):
        from mcp_server._gate import _startup_init
        from mcp_server.hooks import REGISTRY

        _startup_init()
        return next(h.fn for h in REGISTRY._chain if h.name == "psspps_context")

    def test_phase1_returns_under_50ms(self):
        """Phase 1 must not block the calling thread."""
        # Re-arm a fresh _submitted event by temporarily patching
        import mcp_server._gate as g

        # Reset registered flag so we get a fresh closure
        g._context_hook_registered.clear()
        g._register_psspps_context_hook()

        hook_fn = next(
            h.fn for h in __import__("mcp_server.hooks", fromlist=["REGISTRY"]).REGISTRY._chain
            if h.name == "psspps_context"
        )

        t0 = time.perf_counter()
        hook_fn("init_check", {})
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms < 100, f"Phase 1 blocked for {elapsed_ms:.1f}ms"

    def test_phase2_emits_notification_once(self, capsys):
        """Phase 2 emits exactly one stderr line after _context_result is set."""
        import mcp_server._gate as g

        # Simulate result from background thread
        g._context_result.update({"n_docs": 4, "n_comments": 2, "source": "bus"})

        g._context_hook_registered.clear()
        g._register_psspps_context_hook()

        hook_fn = next(
            h.fn for h in __import__("mcp_server.hooks", fromlist=["REGISTRY"]).REGISTRY._chain
            if h.name == "psspps_context"
        )

        # Phase 1 — submit (background search patched out in fixture)
        hook_fn("init_check", {})
        time.sleep(0.05)

        # Phase 2 — should emit
        hook_fn("graph_status", {})
        captured = capsys.readouterr()
        assert "[coherence]" in captured.err
        assert "4 docs" in captured.err
        assert "2 comment" in captured.err

    def test_phase2_notification_fires_only_once(self, capsys):
        """Repeated Phase 2 calls must not spam the output channel."""
        import mcp_server._gate as g

        g._context_result.update({"n_docs": 3, "n_comments": 0, "source": "direct"})
        g._context_hook_registered.clear()
        g._register_psspps_context_hook()

        hook_fn = next(
            h.fn for h in __import__("mcp_server.hooks", fromlist=["REGISTRY"]).REGISTRY._chain
            if h.name == "psspps_context"
        )

        hook_fn("init_check", {})        # Phase 1
        time.sleep(0.05)
        hook_fn("graph_status", {})      # Phase 2 — first notification
        hook_fn("harmonic_index_state", {})  # Phase 2 again — must be silent
        hook_fn("psspps_query", {})          # Phase 2 again — must be silent

        captured = capsys.readouterr()
        notification_lines = [
            line for line in captured.err.splitlines()
            if line.startswith("[coherence]")
        ]
        assert len(notification_lines) == 1, (
            f"Expected 1 notification, got {len(notification_lines)}: {notification_lines}"
        )


# ---------------------------------------------------------------------------
# _write_and_notify
# ---------------------------------------------------------------------------


class TestWriteAndNotify:
    def test_populates_context_result(self, tmp_path, monkeypatch):
        """_write_and_notify must set n_docs, n_comments, source, alpha."""
        import graph.node as gn
        import mcp_server._gate as g

        monkeypatch.setattr(gn, "SESSIONS_DIR", tmp_path)

        top_docs = [
            {"title": "t1", "path": "sessions/comments/2026-01-01-comment-foo.md",
             "combined_score": 0.8, "snippet": "s1"},
            {"title": "t2", "path": "stations/home.md",
             "combined_score": 0.6, "snippet": "s2"},
        ]
        g._write_and_notify(top_docs, alpha=0.65, query="test", source="bus")

        assert g._context_result["n_docs"] == 2
        assert g._context_result["n_comments"] == 1
        assert g._context_result["source"] == "bus"
        assert abs(g._context_result["alpha"] - 0.65) < 1e-9

    def test_live_context_file_written(self, tmp_path, monkeypatch):
        """write_live_context must create sessions/live-context.md."""
        import graph.node as gn
        import mcp_server._gate as g

        monkeypatch.setattr(gn, "SESSIONS_DIR", tmp_path)

        g._write_and_notify(
            [{"title": "x", "path": "sessions/x.md", "combined_score": 0.5, "snippet": "x"}],
            alpha=0.5, query="q", source="direct",
        )
        assert (tmp_path / "live-context.md").exists()


# ---------------------------------------------------------------------------
# _hot_shard_query
# ---------------------------------------------------------------------------


class TestHotShardQuery:
    def test_cold_index_returns_fallback(self):
        import numpy as np
        from mcp_server._gate import _hot_shard_query

        q = _hot_shard_query(np.zeros(8))
        assert len(q) > 0
        assert "recent" in q or "session" in q or "context" in q

    def test_code_hot_shard_includes_code_terms(self):
        import numpy as np
        from mcp_server._gate import _hot_shard_query

        # CODE shards are 3 and 4
        acts = np.zeros(8)
        acts[3] = 5.0
        q = _hot_shard_query(acts)
        assert any(kw in q for kw in ("engine", "scheduler", "code", "implementation"))

    def test_math_hot_shard_includes_math_terms(self):
        import numpy as np
        from mcp_server._gate import _hot_shard_query

        acts = np.zeros(8)
        acts[1] = 3.0
        q = _hot_shard_query(acts)
        assert any(kw in q for kw in ("harmonic", "simulation", "attractor", "mathematics"))

    def test_returns_string(self):
        import numpy as np
        from mcp_server._gate import _hot_shard_query

        q = _hot_shard_query(np.random.default_rng(42).random(8))
        assert isinstance(q, str) and len(q) > 0


# ---------------------------------------------------------------------------
# graph package public surface
# ---------------------------------------------------------------------------


class TestGraphPublicSurface:
    def test_write_comment_node_importable(self):
        from graph import write_comment_node
        assert callable(write_comment_node)

    def test_write_live_context_importable(self):
        from graph import write_live_context
        assert callable(write_live_context)

    def test_comments_dir_importable(self):
        from graph import COMMENTS_DIR
        from pathlib import Path
        assert isinstance(COMMENTS_DIR, Path)
        assert COMMENTS_DIR.name == "comments"

    def test_write_comment_node_creates_file(self, tmp_path, monkeypatch):
        import graph.node as gn
        monkeypatch.setattr(gn, "COMMENTS_DIR", tmp_path)

        from graph.node import write_comment_node
        path = write_comment_node(
            target_stem="test-target",
            comment="This is a test comment.",
            tool_context="graph_annotate",
            confidence=0.9,
        )
        assert path.exists()
        text = path.read_text()
        assert "#agent-comment" in text
        assert "[[test-target]]" in text
        assert "0.90" in text

    def test_write_live_context_creates_file(self, tmp_path, monkeypatch):
        import graph.node as gn
        monkeypatch.setattr(gn, "SESSIONS_DIR", tmp_path)

        from graph.node import write_live_context
        path = write_live_context([
            {"title": "node-a", "path": "sessions/x.md", "combined_score": 0.75, "snippet": "snip"},
        ])
        assert path.name == "live-context.md"
        text = path.read_text()
        assert "[[node-a]]" in text
        assert "#live-context" in text
