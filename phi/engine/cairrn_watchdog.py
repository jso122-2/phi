# -*- coding: utf-8 -*-
"""Compatibility shim — re-exports from phi.engine.cairrn.watchdog.

New code should import directly from phi.engine.cairrn:
    from phi.engine.cairrn import CairrnWorkerWatchdog
"""
# ruff: noqa: F401
from phi.engine.cairrn.watchdog import CairrnWorkerWatchdog
from phi.engine.cairrn._constants import EULER_FLOOR as _EULER_FLOOR

__all__ = ["CairrnWorkerWatchdog", "_EULER_FLOOR"]
