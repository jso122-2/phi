# -*- coding: utf-8 -*-
"""pipeline.worker.executor — parallel download thread pool.

Drains a list of Jobs using N threads.  Each thread calls
download_track() for every track in the job, trying sources in
priority order.

Multi-pass retry
----------------
Up to `retry_passes` retry rounds for failed tracks between passes.
Pass 1 failure → wait pass_delays_s[0] → pass 2
Pass 2 failure → wait pass_delays_s[1] → pass 3
...

Summary
-------
run_workers() returns a WorkerSummary with per-job counts of
ok/failed tracks and per-track DownloadResult objects.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

from pipeline.fetcher.models import Job, TrackInfo
from pipeline.sources import DEFAULT_SOURCES
from pipeline.sources.base import DownloadResult, Source
from pipeline.worker.multi_source import download_track

log = logging.getLogger(__name__)


@dataclass
class TrackResult:
    track:   TrackInfo
    result:  DownloadResult
    attempt: int


@dataclass
class JobResult:
    job:     Job
    ok:      list[TrackResult]    = field(default_factory=list)
    failed:  list[TrackResult]    = field(default_factory=list)

    @property
    def n_ok(self) -> int:
        return len(self.ok)

    @property
    def n_failed(self) -> int:
        return len(self.failed)


@dataclass
class WorkerSummary:
    jobs:        list[JobResult]  = field(default_factory=list)

    @property
    def total_ok(self) -> int:
        return sum(j.n_ok for j in self.jobs)

    @property
    def total_failed(self) -> int:
        return sum(j.n_failed for j in self.jobs)


def _process_job(
    job:           Job,
    sources:       Sequence[Source],
    proxy:         Optional[str],
    timeout_s:     int,
    retry_passes:  int,
    pass_delays_s: list[int],
) -> JobResult:
    """Process a single Job across all retry passes.  Called from thread pool."""
    job_result = JobResult(job=job)
    pending: list[TrackInfo] = list(job.tracks)

    for pass_num in range(1, retry_passes + 1):
        if not pending:
            break
        if pass_num > 1:
            delay = pass_delays_s[pass_num - 2] if (pass_num - 2) < len(pass_delays_s) else pass_delays_s[-1]
            log.info("job %r pass %d/%d — waiting %ds before retry (%d tracks)",
                     job.id, pass_num, retry_passes, delay, len(pending))
            time.sleep(delay)

        still_failing: list[TrackInfo] = []
        for track in pending:
            dr = download_track(
                track=track,
                output_dir=job.output_dir,
                sources=sources,
                fmt=job.fmt,
                proxy=proxy,
                timeout_s=timeout_s,
            )
            tr = TrackResult(track=track, result=dr, attempt=pass_num)
            if dr.ok:
                job_result.ok.append(tr)
            else:
                still_failing.append(track)
                # Replace any earlier failure record with this one
                job_result.failed = [f for f in job_result.failed if f.track is not track]
                job_result.failed.append(tr)

        pending = still_failing

    return job_result


def run_workers(
    jobs:           Sequence[Job],
    *,
    n_threads:      int             = 4,
    retry_passes:   int             = 3,
    pass_delays_s:  list[int]       = None,
    pass_timeout_s: int             = 600,
    proxy:          Optional[str]   = None,
    sources:        Optional[Sequence[Source]] = None,
) -> WorkerSummary:
    """
    Run download jobs in parallel using a ThreadPoolExecutor.

    Parameters
    ----------
    jobs            : list of Job objects (each contains a list of TrackInfo)
    n_threads       : parallel workers
    retry_passes    : number of download attempts per job (default 3)
    pass_delays_s   : seconds to wait between passes (default [20, 90])
    pass_timeout_s  : per-pass SIGKILL timeout for yt-dlp (default 600)
    proxy           : optional SOCKS5 proxy URL for youtube_music + youtube sources
    sources         : override default source list (default: DEFAULT_SOURCES)

    Returns
    -------
    WorkerSummary with per-job and aggregate ok/failed counts.
    """
    if pass_delays_s is None:
        pass_delays_s = [20, 90]
    if sources is None:
        sources = DEFAULT_SOURCES

    summary = WorkerSummary()

    if not jobs:
        log.info("run_workers: no jobs to process")
        return summary

    log.info(
        "run_workers: %d job(s), %d thread(s), %d pass(es), proxy=%s",
        len(jobs), n_threads, retry_passes, proxy or "none",
    )

    with ThreadPoolExecutor(max_workers=n_threads, thread_name_prefix="phi-dl") as pool:
        futures = {
            pool.submit(
                _process_job,
                job, sources, proxy, pass_timeout_s, retry_passes, pass_delays_s,
            ): job
            for job in jobs
        }

        for future in as_completed(futures):
            job = futures[future]
            try:
                job_result = future.result()
            except Exception as exc:
                log.exception("job %r crashed: %s", job.id, exc)
                job_result = JobResult(job=job)

            summary.jobs.append(job_result)
            log.info(
                "job %r done: %d ok / %d failed",
                job.id, job_result.n_ok, job_result.n_failed,
            )

    log.info(
        "run_workers complete: %d total ok / %d total failed",
        summary.total_ok, summary.total_failed,
    )
    return summary
