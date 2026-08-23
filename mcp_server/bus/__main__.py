"""Worker entry: mmap consume loop plus an auto-hosted celery worker connection."""
from __future__ import annotations

import logging
import os
import sys
import threading


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[bus-worker] %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    os.environ["MCP_BUS_WORKER"] = "1"

    from mcp_server.bus.celery_app import app
    from mcp_server.bus.consumer import consume_forever
    from mcp_server.bus.runtime import ensure_runtime

    ensure_runtime()
    stop = threading.Event()
    mmap_thread = threading.Thread(
        target=consume_forever,
        args=(stop,),
        name="mmap-consumer",
        daemon=True,
    )
    mmap_thread.start()

    if app is not None:
        try:
            app.worker_main([
                "worker",
                "--pool=solo",
                "--concurrency=1",
                "--loglevel=info",
                "--without-heartbeat",
                "--without-mingle",
                "--without-gossip",
                "--hostname=spotify-rip-bus@%h",
            ])
            return
        except SystemExit:
            raise
        except Exception:
            logging.exception("celery worker_main failed; mmap consumer continues")

    try:
        mmap_thread.join()
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()
