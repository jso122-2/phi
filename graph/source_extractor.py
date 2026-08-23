"""
source_extractor.py — parse Python source files into IngestedDoc objects.

Uses Python's ast module to extract:
  - Module docstring (becomes the node body)
  - Top-level class and function names + their docstrings
  - Import graph (informs wikilink suggestions)
  - Package / module metadata (tags, hub assignment)

Produces one IngestedDoc per .py file, ready to pass to IngestionPipeline.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from graph.ingestion import IngestedDoc
from graph.node import VAULT_ROOT

# Packages that map to known vault hub tags
_PACKAGE_HUB: dict[str, str] = {
    "graph":       "CODE",
    "mcp_server":  "CODE",
    "engine":      "CODE",
    "workers":     "CODE",
    "sims":        "MATH",
    "cognitive":   "CODE",
    "models":      "MATH",
    "pipeline":    "CODE",
    "psspps":      "CODE",
    "scripts":     "CODE",
    "tools":       "CODE",
    "config":      "COMMANDS",
    "phi":         "CODE",
}

# Packages to skip entirely (tests, cache, build artefacts)
_SKIP_PACKAGES: frozenset[str] = frozenset({
    "tests", "__pycache__", ".pytest_cache", ".git", ".hub.git",
    "node_modules", ".obsidian", "phi.app",
})

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str, max_len: int = 48) -> str:
    return _SLUG_RE.sub("-", text.lower()[:max_len]).strip("-") or "untitled"


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _module_docstring(tree: ast.Module) -> str:
    return ast.get_docstring(tree) or ""


def _top_level_items(tree: ast.Module) -> list[tuple[str, str, str]]:
    """
    Return (kind, name, docstring) for every top-level class / function.
    kind ∈ {"class", "def", "async def"}
    """
    items: list[tuple[str, str, str]] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            doc = ast.get_docstring(node) or ""
            items.append(("class", node.name, doc[:300]))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            doc = ast.get_docstring(node) or ""
            items.append((kind, node.name, doc[:300]))
    return items


def _imports(tree: ast.Module) -> list[str]:
    """Return all locally-scoped module names (e.g. 'graph.node', 'sims.harmonic')."""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            # Keep only intra-project imports (no dotted stdlib / third-party)
            parts = node.module.split(".")
            if parts[0] in _PACKAGE_HUB:
                found.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] in _PACKAGE_HUB:
                    found.append(alias.name)
    return list(dict.fromkeys(found))  # deduplicated, order-preserving


# ---------------------------------------------------------------------------
# Per-file extraction
# ---------------------------------------------------------------------------


_WIKILINK_SANITIZE_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _sanitize_wikilinks(text: str) -> str:
    """Escape [[...]] patterns in raw text so they don't create false vault links."""
    return _WIKILINK_SANITIZE_RE.sub(r"`[[\1]]`", text)


def extract_module(path: Path) -> IngestedDoc | None:
    """
    Parse a single .py file into an IngestedDoc.
    Returns None for files that are empty, stubs, or parse failures.
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    if len(source.strip()) < 10:
        return None  # skip empty __init__.py stubs

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    # Determine package and relative path label
    try:
        rel = path.relative_to(VAULT_ROOT)
        parts = rel.parts          # e.g. ("engine", "gate.py") or ("mcp_server", "tools", "graph.py")
        package = parts[0]
        sub = "/".join(parts[1:]).removesuffix(".py")   # e.g. "tools/graph" or "node"
        label = f"{package}/{sub}"                       # e.g. "engine/gate" or "graph/node"
    except ValueError:
        package = path.parent.name
        sub = path.stem
        label = f"{package}/{sub}"

    if package in _SKIP_PACKAGES:
        return None

    module_doc = _sanitize_wikilinks(_module_docstring(tree))
    items_raw = _top_level_items(tree)
    items = [(k, n, _sanitize_wikilinks(d)) for k, n, d in items_raw]
    import_names = _imports(tree)

    # ── Build vault-ready text ─────────────────────────────────────────────
    lines: list[str] = []

    lines.append(f"**Package:** `{package}`  ")
    lines.append(f"**Module:** `{label}`  ")
    lines.append(f"**Source:** `{path.relative_to(VAULT_ROOT)}`")
    lines.append("")

    if module_doc:
        lines.append(module_doc)
        lines.append("")

    if items:
        lines.append("## API")
        lines.append("")
        for kind, name, doc in items:
            sig = f"`{kind} {name}`"
            if doc:
                short = doc.split("\n")[0][:120]
                lines.append(f"- {sig} — {short}")
            else:
                lines.append(f"- {sig}")
        lines.append("")

    if import_names:
        lines.append("## Internal imports")
        lines.append("")
        lines.append(", ".join(f"`{m}`" for m in import_names[:12]))
        lines.append("")

    # Tags
    tags = ["code", "module", _slug(package)]
    hub_tag = _PACKAGE_HUB.get(package, "CODE")
    tags.append(_slug(hub_tag.lower()))

    metadata: dict[str, Any] = {
        "source_path": str(path.relative_to(VAULT_ROOT)),
        "package": package,
        "module": label,
        "hub": hub_tag,
        "created_ts": "",   # let pipeline auto-timestamp
    }

    return IngestedDoc(
        title=label,
        text="\n".join(lines),
        tags=tags,
        metadata=metadata,
        stem_override=_slug(label),
    )


# ---------------------------------------------------------------------------
# Batch extraction
# ---------------------------------------------------------------------------


@dataclass
class SourceScanResult:
    docs: list[IngestedDoc] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "extracted": len(self.docs),
            "skipped": len(self.skipped),
            "errors": len(self.errors),
        }


def scan_source(
    packages: list[str] | None = None,
    vault_root: Path | None = None,
    skip_tests: bool = True,
    skip_init_stubs: bool = True,
) -> SourceScanResult:
    """
    Scan source packages and return IngestedDocs.

    Parameters
    ----------
    packages    : list of package directory names to scan (default: all known packages)
    vault_root  : override VAULT_ROOT (for testing)
    skip_tests  : skip files under tests/ directory
    skip_init_stubs : skip near-empty __init__.py files
    """
    root = vault_root or VAULT_ROOT
    result = SourceScanResult()

    target_packages = packages or list(_PACKAGE_HUB.keys())

    for pkg in target_packages:
        pkg_dir = root / pkg
        if not pkg_dir.is_dir():
            result.skipped.append(f"{pkg}/ (directory not found)")
            continue

        for py_file in sorted(pkg_dir.rglob("*.py")):
            # Skip __pycache__ and test files
            if "__pycache__" in py_file.parts:
                continue
            if skip_tests and "tests" in py_file.parts:
                continue
            # Skip __init__ stubs with < 5 lines of real content
            if skip_init_stubs and py_file.name == "__init__.py":
                try:
                    content = py_file.read_text(encoding="utf-8", errors="replace").strip()
                    if len(content.splitlines()) < 5:
                        result.skipped.append(str(py_file.relative_to(root)))
                        continue
                except OSError:
                    pass

            doc = extract_module(py_file)
            if doc is None:
                result.skipped.append(str(py_file.relative_to(root)))
            else:
                result.docs.append(doc)

    return result
