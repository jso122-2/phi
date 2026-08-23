from .walk import order_neighbors
from .scheduler import AdaptiveTopologyScheduler
from .log import setup_logger, MetricLogger

__all__ = [
    "order_neighbors",
    "AdaptiveTopologyScheduler",
    "setup_logger",
    "MetricLogger",
    "ReplayBuffer",
    "GraphSnapshot",
    "generate_synthetic_snapshot",
    "prefill_buffer_synthetic",
    "PerpetualTrainer",
    "EMAModel",
]

_LAZY = {
    "ReplayBuffer": ".replay",
    "GraphSnapshot": ".replay",
    "generate_synthetic_snapshot": ".replay",
    "prefill_buffer_synthetic": ".replay",
    "PerpetualTrainer": ".perpetual",
    "EMAModel": ".perpetual",
}


def __getattr__(name: str):
    """Replay + perpetual pull torch; keep log/scheduler importable without it."""
    mod_name = _LAZY.get(name)
    if mod_name is None:
        raise AttributeError(f"module 'phi.utils' has no attribute {name!r}")
    import importlib
    mod = importlib.import_module(mod_name, __name__)
    value = getattr(mod, name)
    globals()[name] = value
    return value
