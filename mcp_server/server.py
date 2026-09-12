"""spotify-rip MCP server — stdio and HTTP dispatcher over the mmap/celery bus.

Transport selection
-------------------
Pass ``--transport sse`` or ``--transport streamable-http`` (or set the
``MCP_TRANSPORT`` environment variable) to run the server as an HTTP endpoint
instead of the default stdio mode.  The host and port are controlled by
``MCP_HOST`` (default ``127.0.0.1``) and ``MCP_PORT`` (default ``8000``).

For cloud serving, launch with::

    MCP_HOST=0.0.0.0 MCP_PORT=8000 python -m mcp_server --transport sse
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import traceback
from typing import Literal

import mcp_server.tools  # noqa: F401 — registers all @mcp.tool() decorators
from mcp_server._gate import _startup_init
from mcp_server._state import mcp

# Open the session gate *after* tools have registered and *before* the
# transport loop starts.
_startup_init()

logging.getLogger("mcp").setLevel(logging.WARNING)
logging.getLogger("mcp.server").setLevel(logging.WARNING)

_TRANSPORTS = ("stdio", "sse", "streamable-http")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mcp_server",
        description="spotify-rip MCP server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--transport",
        choices=_TRANSPORTS,
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        help=(
            "Transport protocol: 'stdio' for local Cursor / IDE use; "
            "'sse' or 'streamable-http' for cloud / remote HTTP access. "
            "Also settable via MCP_TRANSPORT env var."
        ),
    )
    return parser.parse_args()


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


def main() -> None:
    args = _parse_args()
    transport: Literal["stdio", "sse", "streamable-http"] = args.transport  # type: ignore[assignment]

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

        if transport != "stdio":
            from mcp_server._state import _MCP_HOST, _MCP_PORT
            print(
                f"[mcp_server] starting HTTP server  transport={transport}  "
                f"host={_MCP_HOST}  port={_MCP_PORT}",
                file=sys.stderr,
            )

        _enqueue_warmups()
        mcp.run(transport=transport)
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
