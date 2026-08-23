"""Celery app bound to a filesystem broker under .runtime/bus/celery."""
from __future__ import annotations

from mcp_server.bus.runtime import celery_dir, ensure_runtime
from mcp_server.bus.tasks import TASKS

try:
    from celery import Celery
except ImportError:  # pragma: no cover
    Celery = None  # type: ignore[misc, assignment]


def _broker_conf() -> dict:
    ensure_runtime()
    d = celery_dir()
    return {
        "broker_url": "filesystem://",
        "broker_transport_options": {
            "data_folder_in": str(d / "in"),
            "data_folder_out": str(d / "out"),
            "data_folder_processed": str(d / "processed"),
        },
        "result_backend": f"file://{d / 'results'}",
        "task_serializer": "json",
        "accept_content": ["json"],
        "result_serializer": "json",
        "timezone": "UTC",
        "enable_utc": True,
        "worker_hijack_root_logger": False,
        "worker_redirect_stdouts": True,
        "worker_redirect_stdouts_level": "INFO",
        "worker_log_color": False,
        "task_always_eager": False,
    }


def make_app():
    """Return the Celery app, or None if celery is not installed."""
    if Celery is None:
        return None
    app = Celery("spotify_rip_bus")
    app.conf.update(_broker_conf())
    for name, fn in TASKS.items():
        app.task(name=name)(fn)
    return app


app = make_app()
