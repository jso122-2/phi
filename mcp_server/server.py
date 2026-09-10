"""spotify-rip MCP server — stdio or Streamable HTTP dispatcher over the mmap/celery bus."""
from __future__ import annotations

import logging
import os
import signal
import sys
import traceback

import mcp_server.tools  # noqa: F401 — registers all @mcp.tool() decorators
from mcp_server._gate import _startup_init
from mcp_server._state import mcp
from mcp_server.cloud import resolve_config, run as run_transport

# Open the session gate *after* tools have registered and *before* the
# transport starts.  Synchronous so the first tools/call cannot race a closed gate.
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


def main(argv: list[str] | None = None) -> None:
    from mcp_server.bus.host import BusHost

    cfg = resolve_config(argv)
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
        if cfg.transport == "stdio":
            print("[mcp_server] transport=stdio", file=sys.stderr)
        else:
            print(
                f"[mcp_server] transport={cfg.transport} "
                f"bind={cfg.host}:{cfg.port}{cfg.mcp_path} "
                f"auth={'bearer' if cfg.token else 'anon'}",
                file=sys.stderr,
            )
        run_transport(mcp, cfg)
    except KeyboardInterrupt:
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[mcp_server] fatal: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
    finally:
        if host is not None:
            host.stop()


if __name__ == "__main__":
    main()
