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

# Layer 2: eagerly emit live-init.md to stderr so the spawn context appears
# in the MCP console even before the first tool call arrives.
try:
    from mcp_server._spawn_gate import _register_spawn_gate, emit_spawn_context
    _register_spawn_gate()   # idempotent — no-op if _startup_init already ran it
    emit_spawn_context()
except Exception as _sg_exc:
    print(f"[mcp_server.cloud] spawn gate skipped: {_sg_exc}", file=sys.stderr)


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


def _print_cloud_telemetry() -> None:
    """
    Print structured startup telemetry to stderr so the MCP console shows
    the cloud environment state before the first tool call.

    Covers:
    - Registered tool count vs Cursor cap (60)
    - House map completeness (tools not in any named house → overflow)
    - Bus worker availability
    - PYTHONPATH / entrypoint confirmation
    """
    import os
    from mcp_server._state import mcp as _mcp
    from mcp_server.dom_queue import DOMRequestQueue
    from mcp_server._state import _dom_queue

    # Tool count
    try:
        tools = _mcp._tool_manager.list_tools()
        n_tools = len(tools)
        cap = 60
        cap_ok = n_tools <= cap
        cap_flag = "✓" if cap_ok else f"✗ OVER by {n_tools - cap}"
        print(
            f"[cloud:telemetry] tools={n_tools}/{cap} {cap_flag}",
            file=sys.stderr, flush=True,
        )
        if not cap_ok:
            tool_names = sorted(t.name for t in tools)
            print(
                f"[cloud:telemetry] tool list: {tool_names}",
                file=sys.stderr, flush=True,
            )
    except Exception as exc:
        print(f"[cloud:telemetry] tool count failed: {exc}", file=sys.stderr, flush=True)

    # House map completeness
    try:
        if hasattr(_dom_queue, "_houses") and _dom_queue._houses:
            all_mapped: set[str] = set()
            for h in _dom_queue._houses.values():
                all_mapped.update(h.tools)
            overflow = [t.name for t in tools if t.name not in all_mapped]
            if overflow:
                print(
                    f"[cloud:telemetry] overflow (no house): {sorted(overflow)}",
                    file=sys.stderr, flush=True,
                )
            else:
                print(
                    f"[cloud:telemetry] house map: all {n_tools} tools routed ✓",
                    file=sys.stderr, flush=True,
                )
    except Exception as exc:
        print(f"[cloud:telemetry] house map check failed: {exc}", file=sys.stderr, flush=True)

    # Bus
    try:
        from mcp_server.bus.client import get_client, worker_alive
        bus_up = get_client() is not None and worker_alive()
        print(
            f"[cloud:telemetry] bus={'up ✓' if bus_up else 'down — in-process fallback active'}",
            file=sys.stderr, flush=True,
        )
    except Exception:
        print("[cloud:telemetry] bus=unknown", file=sys.stderr, flush=True)

    # Env
    pythonpath = os.environ.get("PYTHONPATH", "(not set)")
    print(
        f"[cloud:telemetry] PYTHONPATH={pythonpath}  entrypoint=mcp_server.cloud",
        file=sys.stderr, flush=True,
    )


def main() -> None:
    host = None
    try:
        _print_cloud_telemetry()
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
