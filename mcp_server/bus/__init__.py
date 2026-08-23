"""mcp_server.bus — mmap ring + auto-hosted celery worker.

MCP stdio is a thin dispatcher. Heavy work is a job on the dispatch ring;
the celery worker consumes it and writes a result file + complete-ring tick.
Studio plugins use the same BusClient.
"""
from __future__ import annotations

from mcp_server.bus.client import BusClient, submit_and_maybe_wait
from mcp_server.bus.host import BusHost
from mcp_server.bus.runtime import runtime_dir

__all__ = ["BusClient", "BusHost", "runtime_dir", "submit_and_maybe_wait"]
