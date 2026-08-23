"""
Code-structure tools: code_audit.

Serves both the /modular (packaging) and /refactor (scope analysis) workflows.
All modes are purely read-only static analysis — no files are modified.
"""
from __future__ import annotations

import ast
import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

from mcp_server._gate import requires_init
from mcp_server._state import _dom_queue, mcp

# ---------------------------------------------------------------------------
# Project root — all target paths resolve relative to here
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent.parent

# ---------------------------------------------------------------------------
# Mode constants
# ---------------------------------------------------------------------------

CODE_AUDIT_MODES = frozenset({"inventory", "size", "imports", "api"})
"""
Modes for code_audit():

  inventory (default) — lists every function, class, and module-level constant
                        in the target. The /modular symbol inventory step.
  size                — walks the target directory and flags any .py file that
                        exceeds 150 logical lines (the /modular size contract).
  imports             — extracts all import statements; flags re-exports and
                        star-imports that blur the public API surface.
  api                 — reads __init__.py and reports what is publicly exported
                        vs. what actually exists in the package.
"""

# Logical-line limit from the /modular contract.
_SIZE_LIMIT = 150


# ---------------------------------------------------------------------------
# Helpers — path resolution
# ---------------------------------------------------------------------------


def _resolve_target(target: str) -> Path:
    """
    Resolve a user-supplied target string to an absolute Path.

    Accepts:
      - A Python dotted module path:  "mcp_server.tools.search"
      - A relative file/dir path:     "mcp_server/tools/search.py"
      - A relative dir path:          "psspps"
    """
    p = _PROJECT_ROOT / target
    if p.exists():
        return p.resolve()

    # Try converting dotted module path to a filesystem path
    as_path = _PROJECT_ROOT / target.replace(".", "/")
    if as_path.exists():
        return as_path.resolve()
    if as_path.with_suffix(".py").exists():
        return as_path.with_suffix(".py").resolve()

    raise FileNotFoundError(
        f"Target {target!r} could not be resolved under {_PROJECT_ROOT}"
    )


def _python_files(path: Path) -> list[Path]:
    """Return all .py files under path (or just path itself if a file)."""
    if path.is_file():
        return [path] if path.suffix == ".py" else []
    return sorted(path.rglob("*.py"))


def _logical_lines(source: str) -> int:
    """Count non-empty, non-comment lines."""
    count = 0
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


# ---------------------------------------------------------------------------
# Mode: inventory
# ---------------------------------------------------------------------------


def _audit_inventory(path: Path) -> dict[str, Any]:
    """
    List every function, class, and module-level constant in the target.

    Corresponds to Step 1 of the /modular skill: symbol inventory.
    """
    files = _python_files(path)
    inventory: dict[str, Any] = {}

    for f in files:
        try:
            source = f.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(f))
        except SyntaxError as exc:
            inventory[str(f.relative_to(_PROJECT_ROOT))] = {"error": str(exc)}
            continue

        functions: list[dict[str, Any]] = []
        classes: list[dict[str, Any]] = []
        constants: list[str] = []

        # tree.body contains only top-level statements — no need to walk deeper.
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in node.args.args]
                functions.append({
                    "name":     node.name,
                    "line":     node.lineno,
                    "args":     args,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                    "has_doc":  (
                        bool(node.body)
                        and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                    ),
                })
            elif isinstance(node, ast.ClassDef):
                classes.append({
                    "name":    node.name,
                    "line":    node.lineno,
                    "methods": [
                        m.name for m in node.body
                        if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ],
                    "has_doc": (
                        bool(node.body)
                        and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                    ),
                })
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id.isupper():
                        constants.append(t.id)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id.isupper():
                    constants.append(node.target.id)

        key = str(f.relative_to(_PROJECT_ROOT))
        inventory[key] = {
            "functions":     functions,
            "classes":       classes,
            "constants":     constants,
            "n_functions":   len(functions),
            "n_classes":     len(classes),
            "n_constants":   len(constants),
        }

    return {
        "mode":      "inventory",
        "target":    str(path.relative_to(_PROJECT_ROOT)),
        "n_files":   len(files),
        "inventory": inventory,
    }


# ---------------------------------------------------------------------------
# Mode: size
# ---------------------------------------------------------------------------


def _audit_size(path: Path) -> dict[str, Any]:
    """
    Walk all .py files under target and flag those that exceed _SIZE_LIMIT.

    Corresponds to the /modular contract: no file > 150 logical lines.
    """
    files = _python_files(path)
    results: list[dict[str, Any]] = []
    oversized: list[str] = []

    for f in files:
        try:
            source = f.read_text(encoding="utf-8")
        except Exception as exc:
            results.append({"file": str(f.relative_to(_PROJECT_ROOT)), "error": str(exc)})
            continue

        ll = _logical_lines(source)
        total = len(source.splitlines())
        over = ll > _SIZE_LIMIT
        rel = str(f.relative_to(_PROJECT_ROOT))
        if over:
            oversized.append(rel)
        results.append({
            "file":           rel,
            "logical_lines":  ll,
            "total_lines":    total,
            "over_limit":     over,
            "excess":         max(0, ll - _SIZE_LIMIT),
        })

    results.sort(key=lambda r: r.get("logical_lines", 0), reverse=True)
    return {
        "mode":             "size",
        "target":           str(path.relative_to(_PROJECT_ROOT)),
        "n_files":          len(files),
        "size_limit":       _SIZE_LIMIT,
        "n_oversized":      len(oversized),
        "oversized":        oversized,
        "contract_ok":      len(oversized) == 0,
        "files":            results,
    }


# ---------------------------------------------------------------------------
# Mode: imports
# ---------------------------------------------------------------------------


def _audit_imports(path: Path) -> dict[str, Any]:
    """
    Extract all import statements and flag issues:
      - Star imports (from x import *)
      - Re-exports (imported then re-assigned in __init__.py)
      - Relative imports (cross-package risk)
    """
    files = _python_files(path)
    file_reports: list[dict[str, Any]] = []
    all_star_imports: list[str] = []

    for f in files:
        try:
            source = f.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(f))
        except SyntaxError as exc:
            file_reports.append({
                "file":  str(f.relative_to(_PROJECT_ROOT)),
                "error": str(exc),
            })
            continue

        imports: list[dict[str, Any]] = []
        star_imports: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "kind":   "import",
                        "module": alias.name,
                        "alias":  alias.asname,
                        "line":   node.lineno,
                    })
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [a.name for a in node.names]
                is_star = names == ["*"]
                rel = node.level  # relative import depth
                if is_star:
                    star_imports.append(f"from {module} import *  (line {node.lineno})")
                imports.append({
                    "kind":     "from",
                    "module":   module,
                    "names":    names,
                    "relative": rel,
                    "star":     is_star,
                    "line":     node.lineno,
                })

        rel_path = str(f.relative_to(_PROJECT_ROOT))
        file_reports.append({
            "file":         rel_path,
            "n_imports":    len(imports),
            "star_imports": star_imports,
            "imports":      imports,
        })
        all_star_imports.extend(star_imports)

    return {
        "mode":             "imports",
        "target":           str(path.relative_to(_PROJECT_ROOT)),
        "n_files":          len(files),
        "total_star_imports": len(all_star_imports),
        "star_imports":     all_star_imports,
        "contract_ok":      len(all_star_imports) == 0,
        "files":            file_reports,
    }


# ---------------------------------------------------------------------------
# Mode: api
# ---------------------------------------------------------------------------


def _audit_api(path: Path) -> dict[str, Any]:
    """
    Check what is publicly exported from __init__.py vs. what exists in the package.

    Reports:
      - exported:   names in __all__ or imported in __init__.py
      - defined:    public symbols (no leading _) across all sibling .py files
      - missing:    defined but not exported (potential gap in the public API)
      - phantom:    exported but not found in the package (broken re-export)
    """
    target_dir = path if path.is_dir() else path.parent
    init_file = target_dir / "__init__.py"

    if not init_file.exists():
        return {
            "mode":   "api",
            "target": str(path.relative_to(_PROJECT_ROOT)),
            "error":  "no __init__.py found",
            "hint":   "target must be a package directory",
        }

    # --- Parse __init__.py ---
    try:
        init_src = init_file.read_text(encoding="utf-8")
        init_tree = ast.parse(init_src, filename=str(init_file))
    except SyntaxError as exc:
        return {
            "mode":  "api",
            "target": str(path.relative_to(_PROJECT_ROOT)),
            "error": f"syntax error in __init__.py: {exc}",
        }

    exported: set[str] = set()

    # Collect __all__ entries
    for node in init_tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant):
                                exported.add(elt.value)

    # Collect names imported in __init__.py
    for node in ast.walk(init_tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    exported.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                exported.add(alias.asname or alias.name.split(".")[0])

    # --- Collect public symbols defined in package modules ---
    defined: set[str] = set()
    sibling_files = [
        f for f in target_dir.glob("*.py")
        if f != init_file and not f.name.startswith("_")
    ]
    for f in sibling_files:
        try:
            src = f.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(f))
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    defined.add(node.name)
            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith("_"):
                    defined.add(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and not t.id.startswith("_"):
                        defined.add(t.id)

    missing = sorted(defined - exported)
    phantom = sorted(exported - defined)

    return {
        "mode":        "api",
        "target":      str(target_dir.relative_to(_PROJECT_ROOT)),
        "init_file":   str(init_file.relative_to(_PROJECT_ROOT)),
        "exported":    sorted(exported),
        "defined":     sorted(defined),
        "missing":     missing,
        "phantom":     phantom,
        "contract_ok": not missing and not phantom,
        "n_exported":  len(exported),
        "n_defined":   len(defined),
        "n_missing":   len(missing),
        "n_phantom":   len(phantom),
    }


# ---------------------------------------------------------------------------
# MCP tool
# ---------------------------------------------------------------------------


@mcp.tool()
@requires_init
def code_audit(target: str, mode: str = "inventory") -> dict[str, Any]:
    """
    /modular + /refactor — static code-structure analysis, read-only.

    Modes
    -----
    inventory (default) — symbol inventory: lists every function, class, and
                          module-level constant. The /modular Step 1 audit.
    size                — flags any .py file that exceeds 150 logical lines.
                          Use before packaging to identify candidates for splitting.
    imports             — extracts all imports; flags star-imports and relative
                          imports that blur the public API surface.
    api                 — compares __init__.py exports against the symbols actually
                          defined in the package. Reports missing / phantom exports.

    Parameters
    ----------
    target : module dotted path (e.g. "psspps") or relative file/dir path
             (e.g. "mcp_server/tools/search.py")
    mode   : one of "inventory" | "size" | "imports" | "api"
    """
    if mode not in CODE_AUDIT_MODES:
        return {
            "error":       "unknown_mode",
            "mode":        mode,
            "valid_modes": sorted(CODE_AUDIT_MODES),
        }

    with _dom_queue.gate("code_audit"):
        try:
            path = _resolve_target(target)
        except FileNotFoundError as exc:
            return {
                "error":  "target_not_found",
                "target": target,
                "detail": str(exc),
            }

    if mode == "inventory":
        return _audit_inventory(path)
    elif mode == "size":
        return _audit_size(path)
    elif mode == "imports":
        return _audit_imports(path)
    else:
        return _audit_api(path)
