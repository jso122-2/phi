"""
Slash-only /10 — rate a project or module out of 10.

Read-only static analysis. Not registered as an MCP tool (Cursor catalog
cap 60); dispatched via run_command("/10 [target]").
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from mcp_server._gate import requires_init
from mcp_server._state import _dom_queue
from mcp_server.tools.modular import _PROJECT_ROOT, _logical_lines, _resolve_target

# Axis weights — sum to 10.0
_W_PARSE = 1.0
_W_SIZE = 2.0
_W_DOCS = 1.5
_W_TYPES = 1.5
_W_IMPORTS = 1.0
_W_TESTS = 1.5
_W_SHAPE = 1.5

_SIZE_LIMIT = 150
_GOD_LIMIT = 400
_MAX_FILES = 800
_SKIP_DIRS = frozenset({
    ".git", ".hub.git", "__pycache__", ".venv", "venv", "node_modules",
    ".mypy_cache", ".pytest_cache", ".obsidian", ".mplconfig", ".sim-out",
})


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _is_test_path(path: Path) -> bool:
    if path.name.startswith("test_") or path.name.endswith("_test.py"):
        return True
    return "tests" in path.parts


def _iter_python_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix == ".py" else []
    files: list[Path] = []
    for p in path.rglob("*.py"):
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        files.append(p)
        if len(files) >= _MAX_FILES:
            break
    return sorted(files)


def _has_doc(node: ast.AST) -> bool:
    body = getattr(node, "body", None)
    if not body:
        return False
    first = body[0]
    return (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    )


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _type_credit(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> float:
    args = [
        a for a in (*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs)
        if a.arg not in {"self", "cls"}
    ]
    annotated = sum(1 for a in args if a.annotation is not None)
    arg_frac = annotated / len(args) if args else 1.0
    ret = 1.0 if fn.returns is not None else 0.0
    return 0.5 * arg_frac + 0.5 * ret


def _size_credit(logical_lines: int) -> float:
    if logical_lines <= _SIZE_LIMIT:
        return 1.0
    if logical_lines <= _SIZE_LIMIT * 2:
        return 0.5
    return 0.0


def _grade(score: float) -> str:
    if score >= 9.0:
        return "excellent"
    if score >= 7.5:
        return "solid"
    if score >= 6.0:
        return "decent"
    if score >= 4.0:
        return "rough"
    return "weak"


def _discover_tests(prod_files: list[Path], tests_root: Path) -> tuple[int, int]:
    """Return (matched_modules, n_prod_modules)."""
    if not tests_root.exists():
        return 0, len(prod_files)
    test_names = {p.stem for p in tests_root.rglob("test_*.py")}
    test_names |= {p.stem for p in tests_root.rglob("*_test.py")}
    matched = 0
    for f in prod_files:
        stem = f.stem
        if f.name == "__init__.py":
            stem = f.parent.name
        candidates = {
            f"test_{stem}",
            f"{stem}_test",
            f"test_{stem.replace('-', '_')}",
        }
        if candidates & test_names or any(stem in n for n in test_names):
            matched += 1
    return matched, len(prod_files)


def _resolve(target: str) -> Path:
    t = (target or ".").strip() or "."
    if t in {".", "project", "repo"}:
        return _PROJECT_ROOT
    try:
        return _resolve_target(t)
    except FileNotFoundError:
        stripped = t.removeprefix("Spotify-rip/").removeprefix("Spotify-rip")
        if stripped != t:
            return _resolve(stripped or ".")
        raise


def score_tree(
    path: Path,
    *,
    project_root: Path | None = None,
    tests_root: Path | None = None,
) -> dict[str, Any]:
    """Score a file or directory out of 10. Used by rate_ten and tests."""
    root = project_root or _PROJECT_ROOT
    tests_root = tests_root or (root / "tests")
    files = _iter_python_files(path)
    rel_target = _rel(path, root)

    if not files:
        return {
            "score": 0.0,
            "out_of": 10,
            "grade": "weak",
            "target": rel_target,
            "n_files": 0,
            "verdict": f"{rel_target} — 0.0/10 (no Python files to rate).",
            "axes": {},
            "fixes": ["Point /10 at a .py file or a package directory."],
            "error": "no_python_files",
        }

    scoring_tests = path.name == "tests" or (path.is_dir() and "tests" in path.parts)
    prod = files if scoring_tests else [f for f in files if not _is_test_path(f)]
    if not prod:
        prod = files

    n_ok = 0
    n_star = 0
    size_credits: list[float] = []
    doc_hits = 0
    doc_total = 0
    type_credits: list[float] = []
    god_files: list[str] = []
    parse_errors: list[str] = []
    has_init = False
    has_all = False
    has_mod_doc = False
    oversized: list[str] = []

    for f in prod:
        if f.name == "__init__.py":
            has_init = True
        try:
            source = f.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(f))
        except (OSError, SyntaxError) as exc:
            parse_errors.append(f"{_rel(f, root)}: {exc}")
            size_credits.append(0.0)
            continue
        n_ok += 1
        ll = _logical_lines(source)
        size_credits.append(_size_credit(ll))
        if ll > _SIZE_LIMIT:
            oversized.append(f"{_rel(f, root)} ({ll} ll)")
        if ll > _GOD_LIMIT:
            god_files.append(_rel(f, root))
        if ast.get_docstring(tree):
            has_mod_doc = True
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if _is_public(node.name):
                    doc_total += 1
                    if _has_doc(node):
                        doc_hits += 1
                    type_credits.append(_type_credit(node))
            elif isinstance(node, ast.ClassDef) and _is_public(node.name):
                doc_total += 1
                if _has_doc(node):
                    doc_hits += 1
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "__all__":
                        has_all = True
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
                n_star += 1

    n_prod = len(prod)
    parse_pts = _W_PARSE * (n_ok / n_prod)
    size_pts = _W_SIZE * (sum(size_credits) / n_prod)
    docs_pts = _W_DOCS * ((doc_hits / doc_total) if doc_total else 1.0)
    types_pts = _W_TYPES * ((sum(type_credits) / len(type_credits)) if type_credits else 1.0)
    if n_star == 0:
        import_pts = _W_IMPORTS
    else:
        import_pts = _W_IMPORTS * max(0.0, 1.0 - 0.5 * n_star)

    if scoring_tests:
        test_pts = _W_TESTS
        matched, n_mod = n_prod, n_prod
    else:
        matched, n_mod = _discover_tests(prod, tests_root)
        frac = (matched / n_mod) if n_mod else 0.0
        any_tests = 0.4 if matched else 0.0
        test_pts = _W_TESTS * min(1.0, any_tests + 0.6 * frac)

    in_package = has_init or (path.is_file() and (path.parent / "__init__.py").exists())
    shape = 0.0
    shape += 0.5 if in_package else 0.0
    shape += 0.5 if not god_files else 0.0
    shape += 0.5 if (has_mod_doc or has_all) else 0.0
    shape_pts = _W_SHAPE * (shape / 1.5)

    axes = {
        "parse": {"pts": round(parse_pts, 2), "max": _W_PARSE,
                  "note": f"{n_ok}/{n_prod} files parse"},
        "size": {"pts": round(size_pts, 2), "max": _W_SIZE,
                 "note": f"{sum(1 for c in size_credits if c == 1.0)}/{n_prod} under {_SIZE_LIMIT} ll"},
        "docs": {"pts": round(docs_pts, 2), "max": _W_DOCS,
                 "note": f"{doc_hits}/{doc_total} public symbols documented"},
        "types": {"pts": round(types_pts, 2), "max": _W_TYPES,
                  "note": "return + arg annotations on public functions"},
        "imports": {"pts": round(import_pts, 2), "max": _W_IMPORTS,
                    "note": f"{n_star} star-import(s)"},
        "tests": {"pts": round(test_pts, 2), "max": _W_TESTS,
                  "note": f"{matched}/{n_mod} modules with a matching test"},
        "shape": {"pts": round(shape_pts, 2), "max": _W_SHAPE,
                  "note": "package init, no god-files, module doc / __all__"},
    }

    score = round(sum(a["pts"] for a in axes.values()), 1)
    score = max(0.0, min(10.0, score))
    grade = _grade(score)

    fixes: list[str] = []
    for name, axis in sorted(axes.items(), key=lambda kv: kv[1]["max"] - kv[1]["pts"], reverse=True):
        gap = axis["max"] - axis["pts"]
        if gap < 0.25:
            continue
        if name == "size" and oversized:
            fixes.append(f"Split oversized files: {', '.join(oversized[:4])}")
        elif name == "docs":
            fixes.append("Add docstrings to public functions and classes.")
        elif name == "types":
            fixes.append("Annotate public function arguments and return types.")
        elif name == "imports" and n_star:
            fixes.append("Replace star-imports with explicit names.")
        elif name == "tests":
            fixes.append("Add tests/test_<module>.py covering the public surface.")
        elif name == "parse" and parse_errors:
            fixes.append(f"Fix syntax errors: {parse_errors[0]}")
        elif name == "shape" and god_files:
            fixes.append(f"Break up god-files (> {_GOD_LIMIT} ll): {', '.join(god_files[:3])}")
        elif name == "shape" and not in_package and path.is_dir():
            fixes.append("Add __init__.py so this directory is a package.")

    verdict = f"{rel_target} — {score:.1f}/10 ({grade})."
    if fixes:
        verdict += f" Biggest drag: {fixes[0]}"

    return {
        "score": score,
        "out_of": 10,
        "grade": grade,
        "target": rel_target,
        "n_files": n_prod,
        "n_truncated": len(files) >= _MAX_FILES,
        "verdict": verdict,
        "axes": axes,
        "fixes": fixes[:5],
        "oversized": oversized[:12],
        "parse_errors": parse_errors[:8],
    }


@requires_init
def rate_ten(target: str = ".") -> dict[str, Any]:
    """
    /10 — rate a project or module out of 10.

    Static analysis across parse health, the /modular 150-line size
    contract, docstrings, type hints, star-imports, tests, and package
    shape. Slash-only (Cursor catalog cap 60).

    Parameters
    ----------
    target : dotted module, relative path, or "." for the project root
    """
    with _dom_queue.gate("rate_ten"):
        try:
            path = _resolve(target)
        except FileNotFoundError as exc:
            return {
                "error": "target_not_found",
                "target": target,
                "detail": str(exc),
                "score": 0.0,
                "out_of": 10,
            }
        return score_tree(path)
