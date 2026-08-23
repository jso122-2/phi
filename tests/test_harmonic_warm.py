"""MCP ring stays warm: snapshot path, cold-save skip, gate-open seed."""
from __future__ import annotations

import json

import pytest

from sims.harmonic import HarmonicIndex


class TestSnapshotPath:
    def test_canonical_path_is_vault_root(self):
        from mcp_server._state import _HARMONIC_SNAPSHOT, _VAULT_ROOT

        assert _HARMONIC_SNAPSHOT.name == ".harmonic-snapshot.json"
        assert _HARMONIC_SNAPSHOT.parent == _VAULT_ROOT
        assert (_VAULT_ROOT / "mcp_server" / "_state.py").is_file()


class TestSaveSkipsCold:
    def test_cold_index_does_not_write(self, tmp_path, monkeypatch):
        import mcp_server._state as st

        idx = HarmonicIndex()
        target = tmp_path / ".harmonic-snapshot.json"
        monkeypatch.setattr(st, "_harmonic_index", idx)
        monkeypatch.setattr(st, "_HARMONIC_SNAPSHOT", target)
        st.save_harmonic_snapshot()
        assert not target.exists()

    def test_warm_index_writes(self, tmp_path, monkeypatch):
        import mcp_server._state as st

        idx = HarmonicIndex()
        idx.ensure_warm()
        target = tmp_path / ".harmonic-snapshot.json"
        monkeypatch.setattr(st, "_harmonic_index", idx)
        monkeypatch.setattr(st, "_HARMONIC_SNAPSHOT", target)
        st.save_harmonic_snapshot()
        assert target.exists()
        snap = json.loads(target.read_text())
        total = sum(s["activation"] for s in snap["shards"])
        assert total == pytest.approx(1.0)


class TestEnsureHarmonicWarm:
    def test_seeds_cold_live_index(self, tmp_path, monkeypatch):
        import mcp_server._state as st

        idx = HarmonicIndex()
        target = tmp_path / ".harmonic-snapshot.json"
        monkeypatch.setattr(st, "_harmonic_index", idx)
        monkeypatch.setattr(st, "_HARMONIC_SNAPSHOT", target)
        assert st.ensure_harmonic_warm() is True
        assert not idx.is_cold()
        assert idx.peak_shard().index == 0
        assert target.exists()

    def test_noop_when_already_warm(self, tmp_path, monkeypatch):
        import mcp_server._state as st

        idx = HarmonicIndex()
        idx.inject(3, 2.0)
        target = tmp_path / ".harmonic-snapshot.json"
        monkeypatch.setattr(st, "_harmonic_index", idx)
        monkeypatch.setattr(st, "_HARMONIC_SNAPSHOT", target)
        assert st.ensure_harmonic_warm() is False
        assert idx.shards[3].activation == pytest.approx(2.0)

    def test_restore_then_warm_replaces_cold_snapshot(self, tmp_path, monkeypatch):
        import mcp_server._state as st

        target = tmp_path / ".harmonic-snapshot.json"
        cold = HarmonicIndex().dump_snapshot()
        target.write_text(json.dumps(cold))

        idx = HarmonicIndex()
        monkeypatch.setattr(st, "_harmonic_index", idx)
        monkeypatch.setattr(st, "_HARMONIC_SNAPSHOT", target)
        assert st.restore_harmonic_snapshot() is True
        assert idx.is_cold()
        assert st.ensure_harmonic_warm() is True
        assert not idx.is_cold()
        reloaded = json.loads(target.read_text())
        total = sum(s["activation"] for s in reloaded["shards"])
        assert total == pytest.approx(1.0)
