# -*- coding: utf-8 -*-
"""Compatibility shim — re-exports from phi.engine.cairrn.router.

New code should import directly from phi.engine.cairrn:
    from phi.engine.cairrn import PhiCairrnRouter, RequestKind, DispatchResult
"""
# ruff: noqa: F401
from phi.engine.cairrn.router import (
    PhiCairrnRouter,
    RequestKind,
    DispatchResult,
    REQUEST_HUB as REQUEST_HUB_MAP,
    PAGE_HUB,
)
from phi.engine.cairrn._constants import shard_priority as _shard_priority

__all__ = [
    "PhiCairrnRouter",
    "RequestKind",
    "DispatchResult",
    "REQUEST_HUB_MAP",
    "PAGE_HUB",
    "_shard_priority",
]
