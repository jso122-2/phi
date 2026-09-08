"""
mcp_server.hook_plugins — auto-discovery and loading of hook plugin files.

Hook plugins let any Python file under `.cursor/hooks/` contribute named
hook functions to the append-only pre-tool hook chain without touching the
core server code.

Plugin contract
---------------
A plugin file must expose a module-level callable:

    def register_plugins(registry: HookRegistry) -> None: ...

That function calls ``registry.register(name, description, fn)`` for each
hook it provides.  Re-registering an existing name is a no-op (idempotent),
so calling this multiple times (e.g. on retrigger) is safe.

Discovery
---------
Auto-discovery scans:

    <repo_root>/.cursor/hooks/*.py

Files are processed in sorted order so load precedence is predictable.
Only files whose names match the plugin pattern (end in ``_hook.py`` or are
named exactly ``hooks.py``) are treated as plugins; others are skipped.

Isolation
---------
Each plugin is imported via importlib into a sandboxed module name so it
cannot shadow existing mcp_server modules.  Import errors are caught and
logged to stderr — a bad plugin never prevents the server from starting.

Usage
-----
Call ``load_plugins()`` once at server startup after the REGISTRY base layer
is sealed:

    from mcp_server.hook_plugins import load_plugins
    from mcp_server.hooks import REGISTRY
    load_plugins(REGISTRY)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_server.hooks import HookRegistry

_PLUGIN_SUFFIXES = ("_hook.py",)
_PLUGIN_EXACT = {"hooks.py"}


def _is_plugin(path: Path) -> bool:
    return path.name in _PLUGIN_EXACT or any(
        path.name.endswith(sfx) for sfx in _PLUGIN_SUFFIXES
    )


def _plugin_module_name(path: Path) -> str:
    """Unique, stable module name for the plugin (no .py, no path separators)."""
    slug = path.stem.replace("-", "_").replace(" ", "_")
    return f"_cursor_hook_plugin_{slug}"


def load_plugins(
    registry: "HookRegistry",
    hooks_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Discover and load all hook plugins from ``hooks_dir``.

    Parameters
    ----------
    registry  : HookRegistry to register discovered hooks into
    hooks_dir : defaults to ``<repo_root>/.cursor/hooks/``

    Returns
    -------
    Summary dict::

        {
            "n_loaded": int,       # plugins whose register_plugins() ran OK
            "n_skipped": int,      # files that don't match the plugin pattern
            "n_errors": int,       # files that failed to import or register
            "loaded": [str, ...],  # loaded plugin file names
            "errors": {            # filename → error message
                "bad_hook.py": "...",
            },
        }
    """
    if hooks_dir is None:
        hooks_dir = Path(__file__).resolve().parent.parent / ".cursor" / "hooks"

    loaded: list[str] = []
    errors: dict[str, str] = {}
    skipped = 0

    if not hooks_dir.is_dir():
        return {
            "n_loaded": 0,
            "n_skipped": 0,
            "n_errors": 0,
            "loaded": [],
            "errors": {},
            "hooks_dir": str(hooks_dir),
            "hooks_dir_exists": False,
        }

    plugin_files = sorted(p for p in hooks_dir.glob("*.py") if _is_plugin(p))

    for path in plugin_files:
        mod_name = _plugin_module_name(path)

        # Re-use already-loaded module (idempotent on retrigger).
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
        else:
            spec = importlib.util.spec_from_file_location(mod_name, path)
            if spec is None or spec.loader is None:
                errors[path.name] = "importlib could not create a spec"
                continue
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)  # type: ignore[union-attr]
                sys.modules[mod_name] = mod
            except Exception as exc:
                errors[path.name] = f"{type(exc).__name__}: {exc}"
                print(
                    f"[hook_plugins] {path.name} failed to import: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
                continue

        fn = getattr(mod, "register_plugins", None)
        if fn is None:
            skipped += 1
            continue

        try:
            fn(registry)
            loaded.append(path.name)
            print(
                f"[hook_plugins] loaded {path.name}",
                file=sys.stderr,
                flush=True,
            )
        except Exception as exc:
            errors[path.name] = f"register_plugins raised {type(exc).__name__}: {exc}"
            print(
                f"[hook_plugins] {path.name} register_plugins failed: {exc}",
                file=sys.stderr,
                flush=True,
            )

    return {
        "n_loaded": len(loaded),
        "n_skipped": skipped,
        "n_errors": len(errors),
        "loaded": loaded,
        "errors": errors,
        "hooks_dir": str(hooks_dir),
        "hooks_dir_exists": True,
    }
