"""Cloud Agent MCP entrypoint — stdio FastMCP for vault search + phi tools.

Cloud Agents do not load laptop ``~/.cursor/mcp.json``. Attach this process as
a custom **stdio** MCP in the Cloud Agents MCP dropdown (or API ``mcpServers``):

    name:    phi
    command: python3
    args:    ["-m", "mcp_server.cloud"]
    env:     PYTHONPATH=/workspace, PYTHONUNBUFFERED=1

Search tools (``psspps_query``, ``find_query``) run on the mmap bus when a
worker is up, and **in-process** when it is not — so Cloud VMs do not depend
on celery. Agents must call those MCP tools instead of ad-hoc ``python -c``.
"""
from __future__ import annotations

import os
import signal
import sys
import traceback

# Must land before mcp_server._state constructs FastMCP.
os.environ.setdefault("SPOTIFY_RIP_MCP_NAME", "phi")
os.environ.setdefault("SPOTIFY_RIP_CLOUD_MCP", "1")
os.environ.setdefault("PYTHONUNBUFFERED", "1")

import mcp_server.tools  # noqa: E402,F401 — registers @mcp.tool() catalog
from mcp_server._gate import _startup_init, is_initialized, open_gate  # noqa: E402
from mcp_server._state import mcp  # noqa: E402

_startup_init()
if not is_initialized():
    # Cloud images may miss optional CAIRRN imports; search still needs the gate.
    open_gate()


def _try_bus_host():
    """Start the mmap worker when possible; search falls back in-process if not."""
    try:
        from mcp_server.bus.host import BusHost, set_current_host

        host = BusHost.auto_start()
        set_current_host(host)
        return host
    except Exception as exc:
        print(f"[mcp_server.cloud] bus host skipped: {exc}", file=sys.stderr)
        return None


def main() -> None:
    host = None
    try:
        host = _try_bus_host()
        try:
            from mcp_server.bus.guardian import ensure_guardian

            ensure_guardian(os.getpid())
        except Exception:
            pass

        def _on_term(_signum, _frame):
            if host is not None:
                try:
                    host.stop()
                except Exception:
                    pass
            os._exit(0)

        signal.signal(signal.SIGTERM, _on_term)
        mcp.run()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as exc:
        print(f"[mcp_server.cloud] fatal: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
    finally:
        if host is not None:
            try:
                host.stop()
            except Exception:
                pass


if __name__ == "__main__":
    main()
