"""phi.ui — player UI components.

Imports are intentionally lazy: PySide6 and pygame are optional and must not
be pulled in when phi.ui is imported by headless workers (embed_tracks, GNN
training, MCP server).  Import the specific submodule you need directly:

    from phi.ui.qt import PhiMainWindow    # PySide6 main window (primary UI)
    from phi.ui.app import run_phi_app     # pygame session runner (engine player)
"""

__all__ = ["PhiMainWindow", "PhiApp", "run_phi_app", "run_phi_terminal"]


def __getattr__(name: str):
    if name in ("PhiMainWindow", "PhiApp"):
        from phi.ui.qt.app import PhiMainWindow, PhiApp  # noqa: F401
        return locals()[name]
    if name in ("run_phi_app", "run_phi_terminal"):
        from phi.ui.app import run_phi_app, run_phi_terminal  # noqa: F401
        return locals()[name]
    raise AttributeError(f"module 'phi.ui' has no attribute {name!r}")
