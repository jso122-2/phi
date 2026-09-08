"""Bus task catalog. Import this module to populate TASKS via @task decorators."""
from __future__ import annotations

# Each sub-module registers its tasks into TASKS on import.
import mcp_server.bus.tasks_graph    # noqa: F401
import mcp_server.bus.tasks_notion   # noqa: F401
import mcp_server.bus.tasks_phi     # noqa: F401
import mcp_server.bus.tasks_search   # noqa: F401
import mcp_server.bus.tasks_session  # noqa: F401

from mcp_server.bus._task_registry import TASKS, run_task  # noqa: F401

__all__ = ["TASKS", "run_task"]
