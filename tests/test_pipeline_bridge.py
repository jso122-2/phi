"""
Tests for pipeline.bridge (MmapPipe + Coordinator + PipeWorker)
and pipeline.worker.fs_organizer (FsOrganizer).

All tests are fully offline — no network, no yt-dlp, no Mullvad.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from pipeline.bridge.mmap_pipe import MmapPipe
from pipeline.bridge.coordinator import Coordinator, PipeWorker
from pipeline.fetcher.models import Job, TrackInfo
from pipeline.sources.base import DownloadResult
from pipeline.worker.fs_organizer import FsOrganizer, _unique_dest


# ═══════════════════════════════════════════════════════════════════════════════
# helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _track(name: str = "Test Track", artists: str = "Test Artist") -> TrackInfo:
    return TrackInfo(
        name=name,
        artists=artists,
        album="Test Album",
        spotify_url="https://open.spotify.com/track/abc123",
        duration_ms=210_000,
    )


def _job(job_id: str = "job_001", n_tracks: int = 1, output_dir: Path = Path("/tmp")) -> Job:
    return Job(
        id=job_id,
        name=f"Job {job_id}",
        tracks=[_track(f"Track {i}") for i in range(n_tracks)],
        output_dir=output_dir,
        fmt="mp3",
    )


def _ok_result(track: TrackInfo, path: str = "/tmp/track.mp3") -> DownloadResult:
    return DownloadResult(track=track, source="test", ok=True, path=path)


def _fail_result(track: TrackInfo) -> DownloadResult:
    return DownloadResult(track=track, source="test", ok=False, error="test fail")


# ═══════════════════════════════════════════════════════════════════════════════
# MmapPipe
# ═══════════════════════════════════════════════════════════════════════════════

class TestMmapPipeBasic:
    def test_put_and_get_roundtrip(self):
        pipe = MmapPipe(capacity=4)
        pipe.put(b"hello")
        assert pipe.get(timeout=1.0) == b"hello"
        pipe.close()

    def test_fifo_ordering(self):
        pipe = MmapPipe(capacity=4)
        for i in range(4):
            pipe.put(f"msg{i}".encode())
        for i in range(4):
            assert pipe.get(timeout=1.0) == f"msg{i}".encode()
        pipe.close()

    def test_qsize(self):
        pipe = MmapPipe(capacity=8)
        assert len(pipe) == 0
        pipe.put(b"a")
        pipe.put(b"b")
        assert len(pipe) == 2
        pipe.get(timeout=1.0)
        assert len(pipe) == 1
        pipe.close()

    def test_repr(self):
        pipe = MmapPipe(capacity=16)
        assert "MmapPipe" in repr(pipe)
        pipe.close()


class TestMmapPipeBlocking:
    def test_get_returns_none_on_timeout(self):
        pipe = MmapPipe(capacity=4)
        result = pipe.get(timeout=0.05)
        assert result is None
        pipe.close()

    def test_put_returns_false_when_full(self):
        pipe = MmapPipe(capacity=2)
        assert pipe.put(b"a") is True
        assert pipe.put(b"b") is True
        # Buffer full — should time out
        assert pipe.put(b"c", timeout=0.05) is False
        pipe.close()

    def test_blocking_put_wakes_on_get(self):
        pipe = MmapPipe(capacity=1)
        pipe.put(b"first")

        results = []

        def writer():
            ok = pipe.put(b"second", timeout=2.0)
            results.append(ok)

        t = threading.Thread(target=writer)
        t.start()
        time.sleep(0.05)
        pipe.get(timeout=1.0)  # drain → unblocks writer
        t.join(timeout=2.0)
        assert results == [True]
        pipe.close()

    def test_blocking_get_wakes_on_put(self):
        pipe = MmapPipe(capacity=4)
        received = []

        def reader():
            data = pipe.get(timeout=2.0)
            received.append(data)

        t = threading.Thread(target=reader)
        t.start()
        time.sleep(0.05)
        pipe.put(b"wake")
        t.join(timeout=2.0)
        assert received == [b"wake"]
        pipe.close()


class TestMmapPipeEdgeCases:
    def test_payload_too_large_raises(self):
        pipe = MmapPipe(slot_size=8)  # max_payload = 6 bytes
        with pytest.raises(ValueError, match="too large"):
            pipe.put(b"x" * 10)
        pipe.close()

    def test_invalid_capacity_raises(self):
        with pytest.raises(ValueError, match="capacity"):
            MmapPipe(capacity=0)

    def test_closed_pipe_raises_on_put(self):
        pipe = MmapPipe(capacity=4)
        pipe.close()
        with pytest.raises(RuntimeError, match="closed"):
            pipe.put(b"data")

    def test_closed_pipe_raises_on_get(self):
        pipe = MmapPipe(capacity=4)
        pipe.close()
        with pytest.raises(RuntimeError, match="closed"):
            pipe.get(timeout=0.1)

    def test_wrap_around(self):
        """Ring buffer correctly wraps past capacity boundary."""
        pipe = MmapPipe(capacity=3)
        # Fill and drain twice — exercises the modulo wrap-around.
        for _ in range(2):
            for i in range(3):
                pipe.put(f"m{i}".encode())
            for i in range(3):
                assert pipe.get(timeout=1.0) == f"m{i}".encode()
        pipe.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Coordinator + PipeWorker
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoordinatorEmpty:
    def test_empty_job_list_done_immediately(self):
        dispatch = MmapPipe(capacity=4)
        complete = MmapPipe(capacity=4)
        coord = Coordinator([], dispatch_pipe=dispatch, complete_pipe=complete)
        coord.start()
        assert coord.wait(timeout=1.0) is True
        coord.stop()
        dispatch.close()
        complete.close()


class TestCoordinatorDispatch:
    def test_dispatches_all_job_ids(self):
        jobs = [_job(f"job_{i:03d}") for i in range(3)]
        dispatch = MmapPipe(capacity=16)
        complete = MmapPipe(capacity=16)
        coord = Coordinator(jobs, dispatch_pipe=dispatch, complete_pipe=complete,
                            n_workers=0)
        coord.start()
        time.sleep(0.1)  # give dispatch thread time to push

        received_ids = set()
        while len(dispatch) > 0:
            raw = dispatch.get(timeout=0.1)
            if raw:
                data = json.loads(raw)
                if data.get("job_id"):
                    received_ids.add(data["job_id"])

        assert received_ids == {"job_000", "job_001", "job_002"}
        coord.stop()
        dispatch.close()
        complete.close()

    def test_n_workers_sentinels_sent(self):
        jobs = [_job("only")]
        dispatch = MmapPipe(capacity=16)
        complete = MmapPipe(capacity=16)
        coord = Coordinator(jobs, dispatch_pipe=dispatch, complete_pipe=complete,
                            n_workers=2)
        coord.start()
        time.sleep(0.15)

        msgs = []
        for _ in range(10):
            raw = dispatch.get(timeout=0.05)
            if raw:
                msgs.append(json.loads(raw))

        sentinels = [m for m in msgs if m.get("job_id") is None]
        assert len(sentinels) == 2
        coord.stop()
        dispatch.close()
        complete.close()


class TestCoordinatorOnComplete:
    def test_on_complete_called_for_each_completion(self):
        jobs = [_job(f"j{i}") for i in range(2)]
        dispatch = MmapPipe(capacity=16)
        complete = MmapPipe(capacity=16)
        completed = []

        def cb(job_id, ok, path):
            completed.append((job_id, ok))

        coord = Coordinator(jobs, dispatch_pipe=dispatch, complete_pipe=complete,
                            on_complete=cb)
        coord.start()

        # Manually inject completion records
        for job in jobs:
            complete.put(json.dumps({"job_id": job.id, "ok": True}).encode())

        assert coord.wait(timeout=2.0) is True
        assert len(completed) == 2
        assert all(ok for _, ok in completed)
        coord.stop()
        dispatch.close()
        complete.close()

    def test_wait_returns_false_on_timeout(self):
        jobs = [_job("never-done")]
        dispatch = MmapPipe(capacity=4)
        complete = MmapPipe(capacity=4)
        coord = Coordinator(jobs, dispatch_pipe=dispatch, complete_pipe=complete)
        coord.start()
        result = coord.wait(timeout=0.05)
        assert result is False
        coord.stop()
        dispatch.close()
        complete.close()


class TestPipeWorker:
    def _make_mock_source(self, ok: bool = True, path: str = "/tmp/t.mp3"):
        source = MagicMock()
        source.name = "mock"
        source.download.return_value = DownloadResult(
            track=_track(), source="mock", ok=ok, path=path if ok else None,
            error=None if ok else "boom",
        )
        return source

    def test_worker_processes_job_and_writes_completion(self):
        dispatch = MmapPipe(capacity=8)
        complete = MmapPipe(capacity=8)
        job = _job("w_job_001", n_tracks=1)
        job_map = {job.id: job}

        source = self._make_mock_source(ok=True)
        worker = PipeWorker(dispatch, complete, job_map, [source])
        worker.start()

        dispatch.put(json.dumps({"job_id": job.id}).encode())
        time.sleep(0.2)

        raw = complete.get(timeout=1.0)
        assert raw is not None
        data = json.loads(raw)
        assert data["job_id"] == job.id
        assert data["ok"] is True

        worker.stop()
        worker.join(timeout=2.0)
        dispatch.close()
        complete.close()

    def test_worker_exits_on_sentinel(self):
        dispatch = MmapPipe(capacity=4)
        complete = MmapPipe(capacity=4)
        worker = PipeWorker(dispatch, complete, {}, [])
        worker.start()
        dispatch.put(json.dumps({"job_id": None}).encode())  # sentinel
        worker.join(timeout=2.0)
        assert not worker.is_alive()
        dispatch.close()
        complete.close()

    def test_worker_records_failure(self):
        dispatch = MmapPipe(capacity=4)
        complete = MmapPipe(capacity=4)
        job = _job("fail_job", n_tracks=1)
        job_map = {job.id: job}
        source = self._make_mock_source(ok=False)
        worker = PipeWorker(dispatch, complete, job_map, [source])
        worker.start()
        dispatch.put(json.dumps({"job_id": job.id}).encode())
        time.sleep(0.2)
        raw = complete.get(timeout=1.0)
        assert raw is not None
        data = json.loads(raw)
        assert data["ok"] is False
        assert data["n_fail"] == 1
        worker.stop()
        worker.join(timeout=2.0)
        dispatch.close()
        complete.close()


# ═══════════════════════════════════════════════════════════════════════════════
# FsOrganizer
# ═══════════════════════════════════════════════════════════════════════════════

class TestFsOrganizerOrganize:
    def test_skips_failed_result(self, tmp_path):
        org = FsOrganizer(output_dir=tmp_path)
        result = _fail_result(_track())
        assert org.organize(result) is None

    def test_skips_result_with_no_path(self, tmp_path):
        org = FsOrganizer(output_dir=tmp_path)
        result = DownloadResult(track=_track(), source="t", ok=True, path=None)
        assert org.organize(result) is None

    def test_skips_missing_source_file(self, tmp_path):
        org = FsOrganizer(output_dir=tmp_path)
        result = _ok_result(_track(), path=str(tmp_path / "gone.mp3"))
        assert org.organize(result) is None

    def test_source_already_in_output_dir_no_move(self, tmp_path):
        audio = tmp_path / "Artist - Title.mp3"
        audio.write_bytes(b"fake_audio")
        org = FsOrganizer(output_dir=tmp_path)
        result = _ok_result(_track(), path=str(audio))
        final = org.organize(result)
        assert final == audio
        assert audio.exists()

    def test_moves_from_staging_to_output(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        output = tmp_path / "output"
        output.mkdir()
        src = staging / "track.mp3"
        src.write_bytes(b"audio_data")

        org = FsOrganizer(output_dir=output, staging_dir=staging)
        result = _ok_result(_track(), path=str(src))
        final = org.organize(result)

        assert final is not None
        assert final.parent == output
        assert not src.exists()

    def test_collision_renamed(self, tmp_path):
        output = tmp_path / "output"
        output.mkdir()
        existing = output / "track.mp3"
        existing.write_bytes(b"old")

        staging = tmp_path / "staging"
        staging.mkdir()
        src = staging / "track.mp3"
        src.write_bytes(b"new")

        org = FsOrganizer(output_dir=output, staging_dir=staging)
        result = _ok_result(_track(), path=str(src))
        final = org.organize(result)

        assert final is not None
        assert final != existing
        assert " (2)" in final.name


class TestFsOrganizerM3U:
    def test_creates_m3u_on_first_entry(self, tmp_path):
        audio = tmp_path / "Artist - Title.mp3"
        audio.write_bytes(b"x")
        m3u = tmp_path / "playlist.m3u"

        org = FsOrganizer(output_dir=tmp_path, m3u_path=m3u)
        result = _ok_result(_track("Title", "Artist"), path=str(audio))
        org.organize(result)

        assert m3u.exists()
        content = m3u.read_text()
        assert "#EXTM3U" in content
        assert "#EXTINF:" in content
        assert str(audio.resolve()) in content

    def test_appends_subsequent_entries(self, tmp_path):
        m3u = tmp_path / "pl.m3u"
        org = FsOrganizer(output_dir=tmp_path, m3u_path=m3u)

        for i in range(3):
            audio = tmp_path / f"track_{i}.mp3"
            audio.write_bytes(b"x")
            result = _ok_result(_track(f"Track {i}"), path=str(audio))
            org.organize(result)

        content = m3u.read_text()
        assert content.count("#EXTINF:") == 3

    def test_no_duplicate_entries(self, tmp_path):
        audio = tmp_path / "track.mp3"
        audio.write_bytes(b"x")
        m3u = tmp_path / "pl.m3u"
        org = FsOrganizer(output_dir=tmp_path, m3u_path=m3u)

        result = _ok_result(_track(), path=str(audio))
        org.organize(result)
        org.organize(result)  # second call — should not duplicate

        content = m3u.read_text()
        assert content.count("#EXTINF:") == 1

    def test_skips_m3u_when_path_none(self, tmp_path):
        audio = tmp_path / "track.mp3"
        audio.write_bytes(b"x")
        org = FsOrganizer(output_dir=tmp_path, m3u_path=None)
        result = _ok_result(_track(), path=str(audio))
        org.organize(result)
        # No M3U should have been created
        assert not any(tmp_path.glob("*.m3u"))

    def test_duration_in_extinf(self, tmp_path):
        audio = tmp_path / "t.mp3"
        audio.write_bytes(b"x")
        m3u = tmp_path / "pl.m3u"
        org = FsOrganizer(output_dir=tmp_path, m3u_path=m3u)

        track = _track()
        track.duration_ms = 240_000  # 240 seconds
        result = DownloadResult(track=track, source="t", ok=True, path=str(audio))
        org.organize(result)

        content = m3u.read_text()
        assert "#EXTINF:240," in content


class TestUniqueDestHelper:
    def test_no_collision(self, tmp_path):
        path = tmp_path / "track.mp3"
        assert _unique_dest(path) == path

    def test_collision_appends_suffix(self, tmp_path):
        existing = tmp_path / "track.mp3"
        existing.write_bytes(b"x")
        result = _unique_dest(existing)
        assert result.name == "track (2).mp3"

    def test_multiple_collisions(self, tmp_path):
        for n in ["track.mp3", "track (2).mp3", "track (3).mp3"]:
            (tmp_path / n).write_bytes(b"x")
        result = _unique_dest(tmp_path / "track.mp3")
        assert result.name == "track (4).mp3"
