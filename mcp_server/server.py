"""spotify-rip MCP server — thin stdio dispatcher over the mmap/celery bus."""
from __future__ import annotations

import logging
import os
import signal
import sys
import traceback

import mcp_server.tools  # noqa: F401 — registers all @mcp.tool() decorators
from mcp_server._gate import _startup_init
from mcp_server._state import mcp

# Open the session gate *after* tools have registered and *before* stdio
# starts.  Synchronous so the first tools/call cannot race a closed gate.
_startup_init()

logging.getLogger("mcp").setLevel(logging.WARNING)
logging.getLogger("mcp.server").setLevel(logging.WARNING)


def _enqueue_warmups() -> None:
    try:
        from mcp_server.bus.client import get_client
        client = get_client()
        if client is None:
            return
        client.submit("warmup.corpus", {})
        client.submit("warmup.phi", {})
    except Exception:
        pass


def _start_health_watchdog() -> None:
    """Daemon thread: poll worker liveness every 5 s, restart on death."""
    import threading
    import time

    def _loop() -> None:
        from mcp_server.bus.client import worker_alive
        from mcp_server.bus.host import restart_worker

        while True:
            time.sleep(5)
            try:
                if not worker_alive():
                    restart_worker()
            except Exception:
                pass

    t = threading.Thread(target=_loop, daemon=True, name="bus-health-watchdog")
    t.start()


def main() -> None:
    from mcp_server.bus.host import BusHost

    host = None
    try:
        from mcp_server.bus.host import set_current_host
        host = BusHost.auto_start()
        set_current_host(host)
        from mcp_server.bus.guardian import ensure_guardian

        ensure_guardian(os.getpid())

        def _on_term(_signum, _frame):
            if host is not None:
                host.stop()
            os._exit(0)

        signal.signal(signal.SIGTERM, _on_term)
        _enqueue_warmups()
        _start_health_watchdog()
        mcp.run()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as exc:
        print(f"[mcp_server] fatal: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
    finally:
        if host is not None:
            host.stop()


if __name__ == "__main__":
    main()
