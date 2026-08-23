# -*- coding: utf-8 -*-
"""phi.ui.genre_graph — compatibility shim.

The Tk-era GenreGraphView lived here.  The PySide6 version lives in
phi.ui.qt.genre_graph; this module is retained only for the shared
write_jim_bindings() helper.
"""
from __future__ import annotations

import json
import pathlib


def write_jim_bindings() -> None:
    """Write ~/.phi/jim_bindings.json from the canonical JIM_BINDING_TABLE."""
    try:
        from phi.ui.qt.keys import JIM_BINDING_TABLE
        out = pathlib.Path.home() / ".phi" / "jim_bindings.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            {"section": sec, "key": key, "description": desc}
            for sec, key, desc in JIM_BINDING_TABLE
        ]
        out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass  # non-fatal: help file is cosmetic
