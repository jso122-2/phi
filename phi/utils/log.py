import logging
import sys
from collections import defaultdict
from typing import Dict, List, Optional

try:
    from torch.utils.tensorboard import SummaryWriter
    _TENSORBOARD_OK = True
except ImportError:
    SummaryWriter = None  # type: ignore[assignment,misc]
    _TENSORBOARD_OK = False


def setup_logger(name: str = "samba_gnn", log_dir: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s", "%H:%M:%S")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    if log_dir:
        fh = logging.FileHandler(f"{log_dir}/train.log")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


class MetricLogger:
    """Lightweight metric tracker with optional TensorBoard support."""

    def __init__(self, log_dir: str = "logs/") -> None:
        self.writer = SummaryWriter(log_dir=log_dir) if _TENSORBOARD_OK else None
        self._metrics: Dict[str, List[float]] = defaultdict(list)

    def log(self, tag: str, value: float, step: int) -> None:
        self._metrics[tag].append(value)
        if self.writer is not None:
            self.writer.add_scalar(tag, value, step)

    def log_dict(self, metrics: Dict[str, float], step: int) -> None:
        for k, v in metrics.items():
            self.log(k, v, step)

    def summary(self, tag: str) -> Dict[str, float]:
        vals = self._metrics.get(tag, [])
        if not vals:
            return {}
        return {"min": min(vals), "max": max(vals), "last": vals[-1], "count": len(vals)}

    def close(self) -> None:
        if self.writer is not None:
            self.writer.close()
