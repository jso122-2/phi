# -*- coding: utf-8 -*-
"""phi.ui.qt — PySide6 UI layer for phi.

Replaces phi.ui._app (Tkinter) as the desktop window and widget set.
All business logic (library, queue, player, CAIRRN) is unchanged.

Public surface
--------------
    from phi.ui.qt import PhiMainWindow
"""
from phi.ui.qt.app import PhiMainWindow

__all__ = ["PhiMainWindow"]
