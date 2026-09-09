"""mcp_server.bus — singleton in-process scheduler.

MCP stdio is a thin dispatcher. Heavy work is a job on the scheduler;
the worker thread runs it and keeps the result in memory.
Studio uses the same BusClient.
"""
from __future__ import annotations

from mcp_server.bus.client import BusClient, submit_and_maybe_wait
from mcp_server.bus.host import BusHost
from mcp_server.bus.runtime import runtime_dir
from mcp_server.bus.scheduler import BusScheduler, ensure_scheduler

__all__ = [
    "BusClient",
    "BusHost",
    "BusScheduler",
    "ensure_scheduler",
    "runtime_dir",
    "submit_and_maybe_wait",
]
