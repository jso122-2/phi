# -*- coding: utf-8 -*-
"""pipeline.bridge — mmap ring-buffer IPC + coordinator for the download pipeline."""
from pipeline.bridge.mmap_pipe import MmapPipe, SharedMmapPipe
from pipeline.bridge.coordinator import Coordinator, PipeWorker

__all__ = ["MmapPipe", "SharedMmapPipe", "Coordinator", "PipeWorker"]
