# -*- coding: utf-8 -*-
"""
pipeline.bridge.coordinator — dispatch + complete daemon threads.

Architecture
------------
Two daemon threads bridge a job deque and a worker pool via two MmapPipe
instances:

    dispatch_pipe  (Coordinator → Workers)
        Coordinator.dispatch_thread pops pending Jobs from the internal deque,
        serialises {job_id} as JSON, and writes to dispatch_pipe.
        Workers read job IDs, look them up in the shared job_map, download,
        then write a completion record to complete_pipe.

    complete_pipe  (Workers → Coordinator)
        Coordinator.complete_thread reads {job_id, ok, path?} records,
        calls the on_complete callback, and increments the done counter.
        When done == total, the done_event is set.

Usage
-----
    from pipeline.bridge.mmap_pipe import MmapPipe
    from pipeline.bridge.coordinator import Coordinator

    dispatch = MmapPipe(capacity=64)
    complete = MmapPipe(capacity=64)

    def on_done(job_id: str, ok: bool, path: str | None) -> None:
        print(f"{job_id}: {'ok' if ok else 'FAIL'} → {path}")

    coord = Coordinator(jobs, dispatch_pipe=dispatch, complete_pipe=complete,
                        on_complete=on_done)
    coord.start()

    # Workers consume dispatch_pipe and write to complete_pipe independently.
    # When all completions arrive:
    coord.wait(timeout=3600)
    coord.stop()

Wire workers with the companion PipeWorker in this module:

    workers = [PipeWorker(dispatch, complete, coord.job_map, sources, proxy)
               for _ in range(n_threads)]
    for w in workers: w.start()
    coord.wait()
    coord.stop()
    for w in workers: w.stop(); w.join()

Sentinel protocol
-----------------
When dispatch_thread exhausts the job deque it pushes N sentinel messages
(one per worker thread it knows about) so every worker exits its poll loop
cleanly.  If n_workers is not passed, sentinels are not sent — workers must
use stop_event instead.
"""
from __future__ import annotations

import json
import logging
import threading
from collections import deque
from typing import Callable, Optional, Sequence

from pipeline.bridge.mmap_pipe import MmapPipe
from pipeline.fetcher.models import Job, TrackInfo
from pipeline.sources.base import DownloadResult, Source
from pipeline.worker.multi_source import download_track

log = logging.getLogger(__name__)

_SENTINEL: bytes = json.dumps({"job_id": None}).encode()
_PUT_TIMEOUT: float = 1.0    # seconds per put attempt before re-checking stop flag
_GET_TIMEOUT: float = 1.0    # seconds per get attempt before re-checking stop flag


# ── Coordinator ────────────────────────────────────────────────────────────────
class Coordinator:
    """
    Dispatch + complete daemon threads bridging a job queue ↔ mmap pipes.

    Parameters
    ----------
    jobs          : sequence of Job objects to process
    dispatch_pipe : MmapPipe workers read job IDs from
    complete_pipe : MmapPipe workers write completion records to
    on_complete   : callback(job_id, ok, path) called for every completed job
    n_workers     : number of PipeWorker threads (used to send N sentinels on
                    dispatch exhaustion); 0 disables sentinel injection
    """

    def __init__(
        self,
        jobs: Sequence[Job],
        *,
        dispatch_pipe: MmapPipe,
        complete_pipe: MmapPipe,
        on_complete: Optional[Callable[[str, bool, Optional[str]], None]] = None,
        n_workers: int = 0,
    ) -> None:
        self._pending: deque[Job] = deque(jobs)
        self.job_map: dict[str, Job] = {j.id: j for j in jobs}
        self._dispatch_pipe = dispatch_pipe
        self._complete_pipe = complete_pipe
        self._on_complete = on_complete
        self._n_workers = n_workers

        self._n_total: int = len(jobs)
        self._n_done: int = 0
        self._lock = threading.Lock()
        self._done_event = threading.Event()
        self._stop_event = threading.Event()

        self._dispatch_thread: Optional[threading.Thread] = None
        self._complete_thread: Optional[threading.Thread] = None

        if self._n_total == 0:
            self._done_event.set()

    # ── lifecycle ──────────────────────────────────────────────────────────────
    def start(self) -> None:
        """Start both daemon threads.  Safe to call once only."""
        if self._dispatch_thread is not None:
            raise RuntimeError("Coordinator already started")

        self._dispatch_thread = threading.Thread(
            target=self._dispatch_loop,
            daemon=True,
            name="coord-dispatch",
        )
        self._complete_thread = threading.Thread(
            target=self._complete_loop,
            daemon=True,
            name="coord-complete",
        )
        self._dispatch_thread.start()
        self._complete_thread.start()
        log.debug(
            "Coordinator started: %d job(s), %d worker(s)",
            self._n_total, self._n_workers,
        )

    def stop(self) -> None:
        """Signal threads to exit and wait for them to finish."""
        self._stop_event.set()
        if self._dispatch_thread:
            self._dispatch_thread.join(timeout=5.0)
        if self._complete_thread:
            self._complete_thread.join(timeout=5.0)

    def wait(self, timeout: Optional[float] = None) -> bool:
        """
        Block until all jobs have been completed (or the timeout expires).

        Returns True if all jobs finished, False on timeout.
        """
        return self._done_event.wait(timeout=timeout)

    @property
    def n_done(self) -> int:
        """Number of completed jobs so far."""
        with self._lock:
            return self._n_done

    # ── dispatch loop ──────────────────────────────────────────────────────────
    def _dispatch_loop(self) -> None:
        log.debug("coord-dispatch: started")
        while not self._stop_event.is_set():
            try:
                job = self._pending.popleft()
            except IndexError:
                break  # all jobs pushed — exit loop

            msg = json.dumps({"job_id": job.id}).encode()
            pushed = False
            while not pushed and not self._stop_event.is_set():
                pushed = self._dispatch_pipe.put(msg, timeout=_PUT_TIMEOUT)

            if not pushed:
                # stop_event fired; put the job back so nothing is silently lost
                self._pending.appendleft(job)
                log.debug("coord-dispatch: aborted (stop requested)")
                return

            log.debug("coord-dispatch: queued job %r", job.id)

        # All jobs dispatched — send a sentinel per worker so each exits cleanly.
        if self._n_workers > 0 and not self._stop_event.is_set():
            for _ in range(self._n_workers):
                self._dispatch_pipe.put(_SENTINEL)
            log.debug("coord-dispatch: sent %d sentinel(s)", self._n_workers)

        log.debug("coord-dispatch: done")

    # ── complete loop ──────────────────────────────────────────────────────────
    def _complete_loop(self) -> None:
        log.debug("coord-complete: started")
        while not self._stop_event.is_set():
            msg = self._complete_pipe.get(timeout=_GET_TIMEOUT)
            if msg is None:
                # Timed out — re-check stop_event and done condition.
                with self._lock:
                    if self._n_done >= self._n_total > 0:
                        break
                continue

            try:
                data: dict = json.loads(msg)
            except json.JSONDecodeError:
                log.warning("coord-complete: malformed message: %r", msg)
                continue

            job_id: Optional[str] = data.get("job_id")
            if job_id is None:
                # Sentinel from a closing worker — ignore in complete loop.
                continue

            ok: bool = bool(data.get("ok", False))
            path: Optional[str] = data.get("path") or None

            if self._on_complete is not None:
                try:
                    self._on_complete(job_id, ok, path)
                except Exception:
                    log.exception("on_complete callback raised for job %r", job_id)

            with self._lock:
                self._n_done += 1
                log.debug(
                    "coord-complete: %r %s (%d/%d)",
                    job_id, "ok" if ok else "FAIL", self._n_done, self._n_total,
                )
                if self._n_done >= self._n_total:
                    self._done_event.set()
                    break

        log.debug("coord-complete: done")


# ── PipeWorker ─────────────────────────────────────────────────────────────────
class PipeWorker(threading.Thread):
    """
    Worker thread that reads job IDs from dispatch_pipe, downloads each Job
    from sources in priority order, and writes a completion record to
    complete_pipe.

    Parameters
    ----------
    dispatch_pipe : MmapPipe to read job IDs from
    complete_pipe : MmapPipe to write completion records to
    job_map       : dict[job_id, Job] — shared reference from Coordinator.job_map
    sources       : ordered list of Source objects to try per track
    proxy         : optional SOCKS5 proxy URL
    timeout_s     : per-track download timeout
    """

    def __init__(
        self,
        dispatch_pipe: MmapPipe,
        complete_pipe: MmapPipe,
        job_map: dict[str, Job],
        sources: Sequence[Source],
        proxy: Optional[str] = None,
        timeout_s: int = 600,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(daemon=True, name=name or "pipe-worker")
        self._dispatch = dispatch_pipe
        self._complete = complete_pipe
        self._job_map = job_map
        self._sources = list(sources)
        self._proxy = proxy
        self._timeout_s = timeout_s
        self._stop_event = threading.Event()

    def run(self) -> None:
        log.debug("%s: started", self.name)
        while not self._stop_event.is_set():
            raw = self._dispatch.get(timeout=_GET_TIMEOUT)
            if raw is None:
                continue

            try:
                data: dict = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("%s: malformed dispatch message: %r", self.name, raw)
                continue

            job_id: Optional[str] = data.get("job_id")
            if job_id is None:
                # Sentinel — coordinator signals no more jobs.
                log.debug("%s: received sentinel, exiting", self.name)
                break

            job = self._job_map.get(job_id)
            if job is None:
                log.error("%s: unknown job_id %r", self.name, job_id)
                continue

            n_ok, n_fail, last_path = self._process_job(job)
            completion = json.dumps({
                "job_id": job_id,
                "ok": n_fail == 0,
                "n_ok": n_ok,
                "n_fail": n_fail,
                "path": last_path,
            }).encode()
            pushed = False
            while not pushed and not self._stop_event.is_set():
                pushed = self._complete.put(completion, timeout=_PUT_TIMEOUT)

        log.debug("%s: stopped", self.name)

    def stop(self) -> None:
        """Signal this worker to exit after its current download finishes."""
        self._stop_event.set()

    def _process_job(self, job: Job) -> tuple[int, int, Optional[str]]:
        """Download all tracks in *job*.  Returns (n_ok, n_fail, last_ok_path)."""
        n_ok = 0
        n_fail = 0
        last_path: Optional[str] = None

        for track in job.tracks:
            result: DownloadResult = download_track(
                track=track,
                output_dir=job.output_dir,
                sources=self._sources,
                fmt=job.fmt,
                proxy=self._proxy,
                timeout_s=self._timeout_s,
            )
            if result.ok:
                n_ok += 1
                last_path = result.path
            else:
                n_fail += 1

        return n_ok, n_fail, last_path
