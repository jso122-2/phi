"""Optional dedicated-process entry: run the singleton scheduler and block."""
from __future__ import annotations

import logging
import sys
import time


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[bus-scheduler] %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    from mcp_server.bus.scheduler import ensure_scheduler

    sched = ensure_scheduler()
    try:
        while sched.alive:
            time.sleep(0.5)
    except KeyboardInterrupt:
        sched.stop()


if __name__ == "__main__":
    main()
