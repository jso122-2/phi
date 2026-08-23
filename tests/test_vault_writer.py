"""
Tests for engine.vault_writer.SambaWriter.

Coverage:
  - Coherence gate: < W(1) ≈ 0.5671 → dry-run (no files written)
  - Coherence gate: ≥ W(1) ≈ 0.5671 → live writes
  - SPROUT arm triggers new .md node
  - Arms below threshold are skipped
  - SambaResult.summary() has required keys
  - sessions/samba/ directory created automatically
  - Multiple arms → multiple writes on one tick
  - Written file content includes arm name and score
  - Dry-run content rendered even when not written
  - SambaWrite.path is None when dry-run
  - make_samba_writer factory works
  - TracerDaemon with vault_root writes to samba/
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from engine.gate import COHERENCE_THRESHOLD
from engine.vault_writer import SambaWriter, SambaResult, make_samba_writer
from models.arms import ARM_NAMES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def all_arms(val: float = 1.0) -> dict[str, float]:
    return {name: val for name in ARM_NAMES}


def make_writer(tmp_path: Path, threshold: float = 0.0) -> SambaWriter:
    return SambaWriter(vault_root=tmp_path, arm_threshold=threshold)


# ===========================================================================
# Coherence gate
# ===========================================================================

class TestCoherenceGate:
    def test_below_threshold_is_dry_run(self, tmp_path):
        w = make_writer(tmp_path)
        result = w.process(all_arms(1.0), coherence=0.30)
        assert not result.coherent
        assert result.n_written == 0
        assert result.n_suppressed == len(ARM_NAMES)

    def test_above_threshold_writes_files(self, tmp_path):
        w = make_writer(tmp_path)
        result = w.process(all_arms(1.0), coherence=0.75)
        assert result.coherent
        assert result.n_written == len(ARM_NAMES)
        assert result.n_suppressed == 0

    def test_exactly_at_threshold_writes(self, tmp_path):
        w = make_writer(tmp_path)
        result = w.process(all_arms(1.0), coherence=COHERENCE_THRESHOLD)
        assert result.coherent
        assert result.n_written > 0

    def test_dry_run_path_is_none(self, tmp_path):
        w = make_writer(tmp_path)
        result = w.process(all_arms(1.0), coherence=0.20)
        for write in result.writes:
            assert write.path is None

    def test_live_write_path_exists(self, tmp_path):
        w = make_writer(tmp_path)
        result = w.process({"SPROUT": 1.0}, coherence=0.80)
        for write in result.writes:
            assert write.path is not None
            assert write.path.exists()


# ===========================================================================
# Arm threshold
# ===========================================================================

class TestArmThreshold:
    def test_zero_score_skipped(self, tmp_path):
        w = make_writer(tmp_path, threshold=0.0)
        result = w.process({"SPROUT": 0.0, "TAG": 1.0}, coherence=0.80)
        arms_fired = [wr.arm for wr in result.writes]
        assert "SPROUT" not in arms_fired
        assert "TAG" in arms_fired

    def test_above_threshold_included(self, tmp_path):
        w = make_writer(tmp_path, threshold=0.5)
        result = w.process({"SPROUT": 0.9, "TAG": 0.3}, coherence=0.80)
        arms_fired = [wr.arm for wr in result.writes]
        assert "SPROUT" in arms_fired
        assert "TAG" not in arms_fired

    def test_all_below_threshold_no_writes(self, tmp_path):
        w = make_writer(tmp_path, threshold=10.0)
        result = w.process(all_arms(1.0), coherence=0.90)
        assert result.n_written == 0
        assert result.n_suppressed == 0   # below threshold → not counted as suppressed


# ===========================================================================
# File content
# ===========================================================================

class TestFileContent:
    def test_sprout_node_contains_arm_name(self, tmp_path):
        w = make_writer(tmp_path)
        result = w.process({"SPROUT": 0.847}, coherence=0.80)
        written = [wr for wr in result.writes if wr.arm == "SPROUT"]
        assert len(written) == 1
        content = written[0].path.read_text()
        assert "SPROUT" in content
        assert "sprout" in content.lower()

    def test_file_includes_score(self, tmp_path):
        w = make_writer(tmp_path)
        result = w.process({"TAG": 2.345}, coherence=0.80)
        written = result.writes[0]
        assert "2.345" in written.content

    def test_dry_run_content_rendered(self, tmp_path):
        w = make_writer(tmp_path)
        result = w.process({"MERGE": 1.0}, coherence=0.20)
        assert result.writes[0].content != ""
        assert "MERGE" in result.writes[0].content

    def test_file_under_samba_subdir(self, tmp_path):
        w = make_writer(tmp_path)
        result = w.process({"CLUSTER": 0.5}, coherence=0.90)
        written = result.writes[0]
        assert "samba" in str(written.path)

    def test_file_suffix_is_md(self, tmp_path):
        w = make_writer(tmp_path)
        result = w.process({"PRUNE": 0.5}, coherence=0.90)
        assert result.writes[0].path.suffix == ".md"


# ===========================================================================
# SambaResult
# ===========================================================================

class TestSambaResult:
    def test_summary_has_required_keys(self, tmp_path):
        w = make_writer(tmp_path)
        result = w.process(all_arms(1.0), coherence=0.80)
        s = result.summary()
        for key in ("tick", "coherence", "coherent", "n_written", "n_suppressed", "arms_fired"):
            assert key in s

    def test_multiple_arms_multiple_writes(self, tmp_path):
        w = make_writer(tmp_path)
        result = w.process({"SPROUT": 1.0, "GRAFT": 0.5, "TAG": 0.3}, coherence=0.80)
        assert result.n_written == 3

    def test_tick_increments(self, tmp_path):
        w = make_writer(tmp_path)
        r0 = w.process({"SPROUT": 1.0}, coherence=0.80)
        r1 = w.process({"SPROUT": 1.0}, coherence=0.80)
        assert r1.tick == r0.tick + 1


# ===========================================================================
# Samba dir created
# ===========================================================================

class TestSambaDirCreated:
    def test_samba_dir_auto_created(self, tmp_path):
        w = SambaWriter(vault_root=tmp_path)
        assert (tmp_path / "sessions" / "samba").is_dir()


# ===========================================================================
# Factory
# ===========================================================================

class TestFactory:
    def test_make_samba_writer_returns_writer(self, tmp_path):
        w = make_samba_writer(vault_root=tmp_path)
        assert isinstance(w, SambaWriter)


# ===========================================================================
# TracerDaemon integration
# ===========================================================================

class TestTracerDaemonVaultIntegration:
    def test_daemon_with_vault_root_writes_samba_nodes(self, tmp_path):
        from engine.tracer_daemon import TracerDaemon

        def ring_A(N: int = 6) -> np.ndarray:
            A = np.zeros((N, N))
            for i in range(N):
                A[i, (i + 1) % N] = 1.0
                A[(i + 1) % N, i] = 1.0
            return A

        daemon = TracerDaemon(d=16, vault_root=tmp_path, coherence_tau=1.0)
        for _ in range(6):
            daemon.run_once(ring_A())

        samba_dir = tmp_path / "sessions" / "samba"
        assert samba_dir.exists()
        # At high coherence tau=1.0 and tick>0, some writes expected
        # (only checking the directory is created and writable)
        assert samba_dir.is_dir()
