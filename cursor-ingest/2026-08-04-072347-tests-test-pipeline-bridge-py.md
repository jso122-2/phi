# tests / test_pipeline_bridge.py

#source #python

> path: tests/test_pipeline_bridge.py  
> ext: .py  

---

# tests / test_pipeline_bridge.py


Tests for pipeline.bridge (MmapPipe + Coordinator + PipeWorker)
and pipeline.worker.fs_organizer (FsOrganizer).

All tests are fully offline — no network, no yt-dlp, no Mullvad.


Defines: _track, _job, _ok_result, _fail_result, TestMmapPipeBasic, TestMmapPipeBlocking, TestMmapPipeEdgeCases, TestCoordinatorEmpty, TestCoordinatorDispatch, TestCoordinatorOnComplete, TestPipeWorker, TestFsOrganizerOrganize, TestFsOrganizerM3U, TestUniqueDestHelper, test_put_and_get_roundtrip, test_fifo_ordering, test_qsize, test_repr, test_get_returns_none_on_timeout, test_put_returns_false_when_full, test_blocking_put_wakes_on_get, test_blocking_get_wakes_on_put, test_payload_too_large_raises, test_invalid_capacity_raises, test_closed_pipe_raises_on_put, test_closed_pipe_raises_on_get, test_wrap_around, test_empty_job_list_done_immediately, test_dispatches_all_job_ids, test_n_workers_sentinels_sent, test_on_complete_called_for_each_completion, test_wait_returns_false_on_timeout, _make_mock_source, test_worker_processes_job_and_writes_completion, test_worker_exits_on_sentinel, test_worker_records_failure, test_skips_failed_result, test_skips_result_with_no_path, test_skips_missing_source_file, test_source_already_in_output_dir_no_move

---

## Semantic links

→ [[pipeline-bridge-coordinator]]
→ [[pipeline-worker-init]]
→ [[pipeline-bridge-init]]
→ [[pipeline-bridge-mmap-pipe]]
→ [[pipeline-worker-fs-organizer]]

## Related notes

→ [[cursor-ingest/2026-08-04-072347-tests-test-vpn-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-workers-base-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-worker-init-py]]
→ [[cursor-ingest/2026-08-04-072347-pipeline-bridge-init-py]]
→ [[cursor-ingest/2026-08-04-072347-tests-test-workers-py]]

→ [[cursor-ingest]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*
