# -*- coding: utf-8 -*-
"""Compatibility shim — re-exports from phi.engine.cairrn.floor.

New code should import directly from phi.engine.cairrn:
    from phi.engine.cairrn import ForestFloor
"""
# ruff: noqa: F401
from phi.engine.cairrn.floor import ForestFloor

__all__ = ["ForestFloor"]
