"""Tests for graph.tracker — usage heat and gitignore hot-set."""
from __future__ import annotations

from pathlib import Path

import graph.tracker as tracker


def setup_function():
    tracker._ledger = None


def teardown_function():
    tracker._ledger = None
    tracker.LEDGER_PATH = tracker.VAULT_ROOT / ".graph-usage.json"


def test_score_weights():
    assert tracker.score({"used": 1, "accessed": 0, "amended": 0}) == 3
    assert tracker.score({"used": 0, "accessed": 3, "amended": 0}) == 3
    assert tracker.score({"used": 0, "accessed": 0, "amended": 1}) == 2


def test_hot_if_used_or_amended(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "LEDGER_PATH", tmp_path / ".graph-usage.json")
    tracker._ledger = {}
    tracker.record("scratch.md", "used")
    assert tracker.is_hot("scratch.md")
    tracker._ledger = {}
    tracker.record("edited.md", "amended")
    assert tracker.is_hot("edited.md")


def test_access_only_needs_three(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "LEDGER_PATH", tmp_path / ".graph-usage.json")
    tracker._ledger = {}
    tracker.record("cold.md", "accessed", n=2)
    assert not tracker.is_hot("cold.md")
    tracker.record("cold.md", "accessed")
    assert tracker.is_hot("cold.md")


def test_sessions_always_hot():
    assert tracker.is_hot("sessions/2026-01-01-foo.md")


def test_live_state_never_tracked():
    assert not tracker.is_hot("live-state.md", hub=True)


def test_gitignore_block_unignores_nested(tmp_path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.pyc\n", encoding="utf-8")
    tracker.write_gitignore(gitignore, ["music/VAULT.md", "HOME.md"])
    text = gitignore.read_text(encoding="utf-8")
    assert tracker.BEGIN in text
    assert "Spotify-rip/*.md" in text
    assert "!Spotify-rip/HOME.md" in text
    assert "!Spotify-rip/music/" in text
    assert "!Spotify-rip/music/VAULT.md" in text
    assert "!Spotify-rip/sessions/**" in text


def test_gitignore_rewrite_is_idempotent(tmp_path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.pyc\n", encoding="utf-8")
    tracker.write_gitignore(gitignore, ["HOME.md"])
    tracker.write_gitignore(gitignore, ["HOME.md", "graph.md"])
    text = gitignore.read_text(encoding="utf-8")
    assert text.count(tracker.BEGIN) == 1
    assert "!Spotify-rip/graph.md" in text
    assert text.startswith("*.pyc")
